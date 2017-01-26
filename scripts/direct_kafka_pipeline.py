#########################################################################
#### This is a script to ingest real time Wikipedia edits via Kafka  ####
#### into Spark Streaming.  The raw edits are saved to an external   ####
#### database, then processed for modeling with SparkMLlib.  The     ####
#### scored results are written to a second external table.  Current ####
#### configs accept batches of data from Kafka every 2 seconds.      ####
#########################################################################

## Import libraries and classes
from __future__ import print_function
import sys
import pandas
import json
import numpy
from pyspark import SparkContext
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import KafkaUtils
from pyspark.sql import *
from pyspark.sql import DataFrameWriter
from pyspark.sql.types import *
from pyspark.sql.functions import *
from pyspark.mllib.regression import LabeledPoint
from pyspark.ml.linalg import Vectors, VectorUDT
from pyspark.ml.feature import PCA, PCAModel
from pyspark.ml.feature import VectorAssembler
from pyspark.mllib.tree import RandomForest, RandomForestModel


#############################
## SPARK CONTEXTS, CONFIGS ##
#############################

## This gives each incoming RDD access to the SparkSQL and DataFrame API, and will 
## allow the session to be restarted in case of driver failure.  It is an 
## implementation detail that the user of the class needs to be aware of.
## Essentially, SparkContext gives us access to Spark, and Spark Session gives us
## access to the DataFrame API.
def getSparkSessionInstance(sparkConf):
    if ('sparkSessionSingletonInstance' not in globals()):
        globals()['sparkSessionSingletonInstance'] = SparkSession\
            .builder\
            .config(conf=sparkConf)\
            .getOrCreate()
    return globals()['sparkSessionSingletonInstance']

## Define scope and print warning if not enough arguments supplied to spark-submit direct_kafka_pipeline.py
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: direct_kafka_pipeline.py <broker_list> <topic>", file=sys.stderr)
        exit(-1)

    sc = SparkContext(appName="PythonStreamingDirectKafkaPipeline")

    ## Stop Spark from printing out endless INFO messages
    sc.setLogLevel("ERROR")

    ## Define various Spark Contexts to use the API
    ssc = StreamingContext(sc, 2)
    sqlContext = SQLContext(sc)
    

###########################################
## DECLARE VARIABLES, LOAD DATA & MODELS ##
###########################################

    iPass = 0

    ## Credentials
    url = 'jdbc:postgresql://127.0.0.1:5432/kafka_streams_wiki_edits'
    mode = 'append'
    properties = {"user":"kafka_streams_user", "password":"postgres"}

    ## Tables we want to access
    raw_table = 'wiki_edits_parsed'
    modeling_table = 'scored_data'
    
    ## DATA ##
    ## Load reference table of historical user counts
    userCountsDF = sqlContext.read.format("csv") \
        .option("header", "true") \
        .option("inferSchema", "true") \
        .load("/PATH_TO_REPO/wiki_edits_user_counts.csv")

    ## Print one time at start of script, this will not happen with 
    ## each RDD
    print('Historical user edit counts from PostgreSQL: \n')
    userCountsDF.show() 

    ## MODELS ##
    ## Principal Components Analysis
    modelPCA = PCAModel.load("/PATH_TO_REPO/models/pca_model.model")
    ignore = ['user', 'isBotEdit']  ## Columns to exclude from PCA

    ## Random Forest for classification
    modelRF = RandomForestModel.load(sc, \
        "/PATH_TO_REPO/models/RFModel")


#######################################
## INGEST AND PROCESS STREAMING DATA ##
#######################################

    num_steps = 12

    ## Create Kafka stream using arguments from command line
    brokers, topic = sys.argv[1:]
    kvs = KafkaUtils.createDirectStream(ssc, [topic], {"metadata.broker.list": brokers})

    ## Load JSON data from Kafka
    lines = kvs.map(lambda x: json.dumps(json.loads(x[1])))

    ## This process will be the computation we perform on each incoming RDD
    def process(time, rdd):
        global iPass

        i = 0
        iPass += 1

        print("========= Microbatch Number: {0} - {1} =========".format(iPass, str(time)))
        try:
        
            # Get the singleton instance of SparkSession
            spark = getSparkSessionInstance(rdd.context.getConf())

            ## Convert JSON to DataFrame, check schema
            editsRDD = sqlContext.read.json(rdd)

            i += 1
            print('Processing RDD, Step {0} of {1}: Schema inferred from JSON: \n'.format(i, num_steps))
            editsRDD.printSchema()

            ## Create a temporary table to run queries
            editsRDD.createOrReplaceTempView("edits")
            editsDF = spark.sql("SELECT * FROM edits")

            i += 1
            print('Processing RDD, Step {0} of {1}: Incoming JSON converted to DataFrame (raw data): \n'.format(++i, num_steps))
            editsDF.show() #works

            ## Write the raw data out to external DB
            try:
                editsDF.write.jdbc(url, raw_table, mode, properties)
            except:
                print("ERROR: Unexpected error writing wiki_edits_parsed to the database; please check url, database, and credentials")
                print("  ", sys.exc_info()[1][1]) # First line of the stack
                ## , sys.exc_info()[0])
                pass

            ## Create categorical column based on byte differential: net decrease or net increase?  
            transformedEditsDF = editsDF.withColumn('addition_or_deletion', editsDF.byteDiff > lit(0).cast('integer'))

            ## Convert the 'type' column to boolean.
            transformedEditsDF = transformedEditsDF.withColumn('type_bool', (transformedEditsDF.type == "EDIT").cast('integer'))  

            ## Update our temporary table with these new features          
            transformedEditsDF.createOrReplaceTempView("edits")

            i += 1
            print('Processing RDD, Step {0} of {1}: Transformed DataFrame with new columns extracted from originals: \n'.format(++i, num_steps))
            transformedEditsDF.show()

            ## Use SparkSQL to further shape our DataFrame:
            ## 1. Filter unwanted columns (like diffUrl)
            ## 2. Cast boolean column types as 0/1 integers
            ## 3. Get the magnitude of edit and length of summary
            filteredEditsDF = spark.sql("""SELECT
                                            user,
                                            type_bool,
                                            length(summary) as summary_bytes,
                                            abs(byteDiff) as total_byte_change,
                                            cast(addition_or_deletion as int),
                                            cast(isBotEdit as int), 
                                            cast(isMinor as int),
                                            cast(isUnpatrolled as int), 
                                            cast(isNew as int)
                                            FROM edits""")

            i += 1
            print('Processing RDD, Step {0} of {1}: Filtered DataFrame with correct column types: \n'.format(++i, num_steps))
            filteredEditsDF.show()
            ## Alt method - userCountsDF = sqlContext.read.jdbc(url = url, table = "user_counts", properties = properties)
            
            ## Join number of edits for each user to filtered DataFrame
            modelDF = filteredEditsDF.join(userCountsDF, "user", 'left')

            ## MISSING VALUES ##
            ## If no edits in historical table, replace with '1'.  Remove any other rows with missing values.
            modelDF = modelDF.fillna({'no_of_edits': 1}).na.drop()

            i += 1
            print('Processing RDD, Step {0} of {1}: Filtered DataFrame joined with userCounts DataFrame for modeling: \n'.format(++i, num_steps))
            modelDF.show() 

            ## MODELING ##
            ## Assembler will append a vector column to the end of the dataframe, ignoring columns in the
            ## `ignore` variable declared above.
            assembler = VectorAssembler(
                inputCols=[x for x in modelDF.columns if x not in ignore],
                outputCol='features')
            modelDF = assembler.transform(modelDF)

            i += 1
            print('Processing RDD, Step {0} of {1}: Modeling DataFrame with features vector: \n'.format(++i, num_steps))
            modelDF.show()

            ## Get components and rename the columns, convert to RDD from DataFrame
            ## for Random Forest
            modelRDD = modelPCA.transform(modelDF) \
                .select(col("pcaFeatures").alias("features"), col("isBotEdit").alias("label")) \
                .rdd
            
            ## Convert to LabeledPoint for RandomForest
            modelRDD = modelRDD.map(lambda r: LabeledPoint(r[1], numpy.array(r[0])))

            i += 1
            print('Processing RDD, Step {0} of {1}: Modeling DataFrame with PCA transformed features vector and target variable: \n'.format(++i, num_steps))
            modelRDD.toDF().show()

            ## Pass that RDD to RandomForest, get predictions and error rate
            predictions = modelRF.predict(modelRDD.map(lambda x: x.features))
            labelsAndPredictions = modelRDD.map(lambda lp: lp.label).zip(predictions)

            i += 1
            print('Processing RDD, Step {0} of {1}: DataFrame with predicted and actual values: \n'.format(++i, num_steps))
            labelsAndPredictions.toDF(["actual", "predicted"]).show()

            testErr = labelsAndPredictions.filter(lambda (v, p): v != p).count() / float(modelDF.count())
            i += 1
            print('Processing RDD, Step {0} of {1}: Test Error = {2}\n'.format(++i, num_steps, testErr))

            ## To join the predictions with the original dataframe, we have to create
            ## an index for each table and join by index.
            predictionsDF = labelsAndPredictions.map(lambda x: Row(predicted = x[1])) \
                .zipWithIndex() \
                .toDF(['predicted', 'index'])

            i += 1
            print('Processing RDD, Step {0} of {1}: Predictions DataFrame with index for joining: \n'.format(++i, num_steps))
            predictionsDF.show()

            ## Need to zip modeling dataframe to provide index for joining with predictions
            zippedModelDF = modelDF.rdd.zipWithIndex().toDF(['cols', 'index'])
            i += 1
            print('\nProcessing RDD, Step {0} of {1}: Modeling (input) DataFrame with index for joining: \n'.format(++i, num_steps))
            zippedModelDF.show()

            ## Create final dataframe and access sub-columns in the schema with dot syntax
            finalDF = zippedModelDF.join(predictionsDF, 'index').select("cols.user", "cols.type_bool", 
                "cols.summary_bytes", "cols.total_byte_change", "cols.addition_or_deletion", 
                "cols.isMinor", "cols.isUnpatrolled", "cols.isNew", "cols.no_of_edits", 
                "cols.isBotEdit", "predicted.predicted")

            i += 1
            print('\nProcessing RDD, Step {0} of {1}: Final DataFrame with scored results and input data joined by index: \n'.format(++i, num_steps))
            finalDF.show()

            ## Write to PostgreSQL
            try:
                finalDF.write.jdbc(url, modeling_table, mode, properties)
            except:
                print("ERROR: Unexpected error writing scored_data to the database; please check url, database, and credentials")
                print("  ", sys.exc_info()[1][1]) # First line of the stack
                ## , sys.exc_info()[0])
                pass

        except:
            pass

    ## Take each incoming RDD from Kafka and pass them through the `process` method
    lines.foreachRDD(process)

    ssc.start()
    ssc.awaitTermination()
