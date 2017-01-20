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

## Needed for 'foreachRDD()' function, further explanation/research required as to why
def getSparkSessionInstance(sparkConf):
    if ('sparkSessionSingletonInstance' not in globals()):
        globals()['sparkSessionSingletonInstance'] = SparkSession\
            .builder\
            .config(conf=sparkConf)\
            .getOrCreate()
    return globals()['sparkSessionSingletonInstance']

## Define scope and print warning if not enough arguments supplied to spark-submit direct_kafka_wordcount.py
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: direct_kafka_wordcount.py <broker_list> <topic>", file=sys.stderr)
        exit(-1)

    sc = SparkContext(appName="PythonStreamingDirectKafkaWordCount")

    ## Stop Spark from printing out endless INFO messages
    sc.setLogLevel("ERROR")

    ## Define various Spark Contexts to use the API
    ssc = StreamingContext(sc, 2)
    sqlContext = SQLContext(sc)

    ## Create Kafka stream using arguments from commmand line
    brokers, topic = sys.argv[1:]
    kvs = KafkaUtils.createDirectStream(ssc, [topic], {"metadata.broker.list": brokers})
    

    ### INGEST ###
    ## Load JSON data from Kafka
    lines = kvs.map(lambda x: json.dumps(json.loads(x[1])))
    
    ## Declare our credentials, tables we want to access, and any queries for PostgreSQL
    url = 'jdbc:postgresql://127.0.0.1:5432/IBM?user=IBM&password=postgres'
    raw_table = 'wiki_edits_parsed'
    modeling_table = 'scored_data'
    mode = 'append'
    properties = {"user":"IBM", "password":"postgres"}

    ## Load reference table of historical user counts
    userCountsDF = sqlContext.read.format("csv") \
        .option("header", "true") \
        .option("inferSchema", "true") \
        .load("/PATH_TO_REPO/wiki_edits_user_counts.csv")

    ## Not working currently ##
    ## This query will retrieve the user counts as they are continually updated from the
    ## stream.  These counts will be joined to the rest of the data for modeling
    ## You could run this once at the start of the stream, or for each RDD.  There are
    ## tradeoffs for each.
    # query = """(SELECT 
    #            "user", 
    #           COUNT('user') AS no_of_edits 
    #         GROUP BY "user") 
    #            AS user_counts"""
    ## Query PostgreSQL and get back most recent user counts

    #userCountsDF = spark.read \
    #    .format("jdbc") \
    #    .option("url", "jdbc:postgresql://127.0.0.1:5432/IBM?user=IBM&password=postgres") \
    #    .option("dbtable", query) \
    #    .option("user", "IBM") \
    #    .option("password", "postgres") \
    #    .load()


    ## Load the pretrained models to score the streaming data
    modelRF = RandomForestModel.load(sc, \
        "/PATH_TO_REPO/models/RFModel")

    modelPCA = PCAModel.load("/PATH_TO_REPO/models/pca_model.model")

    ## Define the columns we want to exclude when doing PCA
    ignore = ['user', 'isBotEdit']

    ## This process will be the computation we perform on each incoming RDD
    def process(time, rdd):
        print("========= %s =========" % str(time))
        try:
        
            # Get the singleton instance of SparkSession
            spark = getSparkSessionInstance(rdd.context.getConf())

            ## Convert JSON to DataFrame, check schema
            editsRDD = sqlContext.read.json(rdd)
            print('Schema inferred from JSON: \n')
            editsRDD.printSchema()
            print('Historical user edit counts from PostgreSQL: \n')
            userCountsDF.show() # works

            ## Create a temporary table to run queries
            editsRDD.createOrReplaceTempView("edits")
            editsDF = spark.sql("SELECT * FROM edits")
            print('Incoming JSON converted to DataFrame (raw data): \n')
            editsDF.show() #works

            editsDF.write.jdbc(url, raw_table, mode, properties)

            ## Create categorical column for type of edit based on byte differential: net decrease
            ## or net increase?  
            transformedEditsDF = editsDF.withColumn('addition_or_deletion', editsDF.byteDiff > lit(0).cast('integer'))

            ## Convert the 'type' column to boolean.
            transformedEditsDF = transformedEditsDF.withColumn('type_bool', (transformedEditsDF.type == "EDIT").cast('integer'))  

            ## Update our temporary table with these new features          
            transformedEditsDF.createOrReplaceTempView("edits")
            print('Transformed DataFrame with new columns extracted from originals: \n')
            transformedEditsDF.show()

            ## If you want to show how SparkSQL returns the same result as showing a DataFrame, run:
            ## spark.sql("select * from edits").show()

            ## This query will transform our DataFrame in several important ways:
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

            print('Filtered DataFrame with correct column types: \n')
            filteredEditsDF.show()
            ## Alt method - userCountsDF = sqlContext.read.jdbc(url = url, table = "user_counts", properties = properties)
            
            ## Join number of edits for each user to filtered DataFrame
            modelDF = filteredEditsDF.join(userCountsDF, "user", 'left')

            ## MISSING VALUES ##
            ## If no edits in historical table, replace with '1'.  Remove any other rows with missing values.
            modelDF = modelDF.fillna({'no_of_edits': 1}).na.drop()
            print('Filtered DataFrame joined with userCounts DataFrame for modeling: \n')
            modelDF.show() 

            ## PCA ##
            ## Assembler will append a vector column to the end of the dataframe
            assembler = VectorAssembler(
                inputCols=[x for x in modelDF.columns if x not in ignore],
                outputCol='features')
            modelDF = assembler.transform(modelDF)

            print('Modeling DataFrame with features vector: \n')
            modelDF.show()

            ## Get components and rename the columns, convert to RDD from DataFrame
            ## for Random Forest
            modelRDD = modelPCA.transform(modelDF) \
                .select(col("pcaFeatures").alias("features"), col("isBotEdit").alias("label")) \
                .rdd
            
            ## Convert to LabeledPoint for RandomForest
            modelRDD = modelRDD.map(lambda r: LabeledPoint(r[1], numpy.array(r[0])))

            print('Modeling DataFrame with PCA transformed features vector and target variable: \n')
            modelRDD.toDF().show()

            ## Pass that RDD to RandomForest
            predictions = modelRF.predict(modelRDD.map(lambda x: x.features))
            labelsAndPredictions = modelRDD.map(lambda lp: lp.label).zip(predictions)
            print('DataFrame with predicted and actual values: \n')
            labelsAndPredictions.toDF(["actual", "predicted"]).show()
            testErr = labelsAndPredictions.filter(lambda (v, p): v != p).count() / float(modelDF.count())
            print('Test Error = ' + str(testErr) + '\n')

            ## To join the predictions with the original dataframe, we have to create
            ## an index for each table and join by index.
            predictionsDF = labelsAndPredictions.map(lambda x: Row(predicted = x[1])) \
                .zipWithIndex() \
                .toDF(['predicted', 'index'])

            print('Predictions DataFrame with index for joining: \n')
            predictionsDF.show()

            zippedModelDF = modelDF.rdd.zipWithIndex().toDF(['cols', 'index'])
            print('\nModeling (input) DataFrame with index for joining: \n')
            zippedModelDF.show()

            finalDF = zippedModelDF.join(predictionsDF, 'index').select("cols.user", "cols.type_bool", 
                "cols.summary_bytes", "cols.total_byte_change", "cols.addition_or_deletion", 
                "cols.isMinor", "cols.isUnpatrolled", "cols.isNew", "cols.no_of_edits", 
                "cols.isBotEdit", "predicted.predicted")

            print('\nFinal DataFrame with scored results and input data joined by index: \n')
            finalDF.show()

            ## Write to PostgreSQL
            finalDF.write.jdbc(url, modeling_table, mode, properties)

        except:
            pass

    lines.foreachRDD(process)

    ssc.start()
    ssc.awaitTermination()







