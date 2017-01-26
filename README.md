# Spark Streaming PoT with Kafka

## Motivation

Create a demo asset that showcases the elegance and power of the Spark API.  The primary data processing script in this demo - `direct_kafka_pipeline.py` - mixes in Spark Streaming, Spark core functions, SparkSQL and Spark Machine Learning.  There are several goals:

1. Connect to real time streaming data with Spark Streaming
2. Data cleansing and feature engineering with SparkSQL
3. Joining traditional RDBMS data sources with streaming data
4. Score each batch of incoming data with Spark MLlib and write the results to an external database

All four of these goals are achieved using Spark, with a handful of popular Python libraries sprinkled in.
______________

## Contents

**Data** - JSON and CSV files of raw and aggregated historical data.

**Models** - PCA and Random Forest models used in `direct_kafka_pipeline.py`.

**jars** - .jar depencies that Spark needs for PostgreSQL & Spark Streaming with Kafka.

**Kafka** - Includes Kafka version 0.10.1.0.

**Scripts** - Contains `postgres_setup.txt` and `direct_kafka_pipeline.py`.


#### Additional Requirements

Please ensure you have installed the following components before working through the setup steps.

1.  [Apache Spark](http://spark.apache.org/downloads.html) - I used version 2.0.0.

2.  [Apache Kafka](https://kafka.apache.org/downloads) - I used version 0.10.1.0

3.  ['hello-kafka-streams'](https://github.com/amient/hello-kafka-streams), a project that connects Kafka to the Wikipedia edits stream via socket.

4.  PostgreSQL - I used the very user friendly [Postgres.app](https://postgresapp.com/) to install and manage PostgreSQL locally.

5.  Python 2.7 - I used [Anaconda](https://www.continuum.io/downloads) for the additional packages.
_______________

## Setup 

After you have installed Spark, Kafka, and followed [the instructions](https://github.com/amient/hello-kafka-streams) to clone 'hello-kafka-streams', open up the terminal.  You are going to create a number of terminal windows to start Zookeeper, Kafka server, Kafka consumer, 'hello-kafka-streams', Spark, and PostgreSQL.  Let's go through those one by one.

### 1. Zookeeper 
Open up a terminal window and navigate to the `/kafka` directory and run the following command:

`./bin/zookeeper-server-start.sh ./config/zookeeper.properties`

This will start the Zookeeper server that Kafka depends on.


### 2. Kafka Server
In a new terminal window, navigate to /kafka and start the Kafka server:

`./bin/kafka-server-start.sh ./config/server.properties`

After printing the config settings for Kafka server you should see a series of info messages with a line like

`[2017-01-17 12:30:01,130] INFO Connecting to zookeeper on localhost:2181 (kafka.server.KafkaServer)`


### 3. hello-kafka-streams

#### Mac/Linux
Open up a third terminal window, and navigate to the /hello-kafka-streams directory.  Once Zookeeper and Kafka Server are running, Kafka Server will be waiting for a stream.  Run the following command to give it one:

`./build/scripts/hello-kafka-streams`

If the script is working properly it should begin to print out a count of edits for each user.  This may take up to 30 seconds to get going, in my experience.  For an in depth tutorial as to how hello-kafka-streams works, please see the original [Confluent.io post](https://www.confluent.io/blog/hello-world-kafka-connect-kafka-streams/).

#### Windows
If you're running this demo on Windows, there are some slight alterations needed to the hello-kafka-streams project. One of the dependencies, *rocksdb*, is set at version 4.4.1 in the project, which does not have support for Windows. This results in never getting to user counts or data coming out of the hello-kafka-streams compiled script. The issue was first reported as fixed in version 4.9.0, so we'll tell the build to use that as the dependency.
 
To fix this, do the following prior to building the hello-kafka-streams project with `./gradlew.bat build`:

1. Open up the file `build.gradle` in the hello-kafka-streams folder
2. Around line 27 there should be a section labeled "dependencies {". At the bottom of that section, but before the closing curly brace "}", paste the following lines, making sure to match the indentation of the original file:

    >`// https://mvnrepository.com/artifact/org.rocksdb/rocksdbjni
    compile group: 'org.rocksdb', name: 'rocksdbjni', version: '4.9.0'`
    
3. Save the file.
4. Go ahead with the build by executing
    `./gradlew.bat build`
    in the terminal from the hello-kafka-streams directory.


### 4. Kafka Consumer
Starting up the Kafka Consumer will allow us to see the raw JSON that is being published to the `wikipedia-edits` topic in Kafka.  Assuming you have successfully completed steps 1-3, starting up the consumer is simple.  

Open up a new terminal window, navigate to your kafka directory, then run

`./bin/kafka-console-consumer.sh —zookeeper localhost —topic wikipedia-parsed`

You should see a stream of JSON start printing after a few moments.


### 5. PostgreSQL Tables
Why don't you go and open up another terminal, because you're gonna need it. Once you've installed PostgreSQL, follow the instructions found in `/scripts/postgres_setup.txt`.  This will set up a database in PostgreSQL with the correct tables and schemas to allow incoming data to be writtento Spark Streaming.  You can test the tables with:

> SELECT * FROM wiki_edits_parsed;
>
> SELECT * FROM user_counts;
> 
> SELECT * FROM scored_data;

You will also need to provide your host:port on line 69, and username/password on lines 69 and 71.


### 6. Spark Submit
Open up yet another terminal (number five, in case you lost count) and navigate to your Spark installation directory.  Before you can submit `direct_kafka_pipeline.py` you'll need to copy the .jar files into the /jar directory for Spark.  For my machine this was `/Users/IBM/desktop/spark2.0/spark-2.0.0-bin-hadoop2.7/jars/`.  You will also need to edit some paths within `direct_kafka_pipeline.py` on the following lines in the script:

Lines 79-82:  Point to `'wiki_edits_user_counts.csv'` from this repo

Lines 91-92: Point to `/models/pca_model.model` from this repo 

Lines 95-96:  Point to `/models/RFModel` from this repo

Once the jars are in the right place and you have the correct paths in the script you are ready to submit `direct_kafka_pipeline.py` to Spark.   When using `spark-submit` you will pass several arguments to the script.  Let's break this down a bit.
 
 1. `--master local[3]` Tells Spark to use the local instance with 3 cores.
 2. `--jars <pathToJarOne>,<pathToJarTwo>` Tells Spark where to look for script dependencies.
 3. `--driver-class-path <pathToDriverJar>` Tells Spark where to look for the PostgreSQL driver.
 4. `/pathTo/direct_kafka_pipeline.py` The script itself to be submitted to Spark.
 5. `localhost:9092`  Host:Port for Kafka Server.
 6. `wikipedia-parsed` Topic to subscribe to within Kafka.

Here is how I submit this job on my machine:

 > `bin/spark-submit --master local[3]  --jars       /Users/IBM/desktop/spark2.0/spark-2.0.0-bin-hadoop2.7/jars/spark-streaming-kafka-0-8-assembly_2.11-2.0.0.jar,/Users/IBM/desktop/spark2.0/spark-2.0.0-bin-hadoop2.7/jars/postgresql-9.4.1212.jre7.jar    --driver-class-path /Users/IBM/desktop/spark2.0/spark-2.0.0-bin-hadoop2.7/jars/postgresql-9.4.1212.jre7.jar     /users/ibm/documents/demos/sparkstreaming/direct_kafka_pipeline.py       localhost:9092 wikipedia-parsed`
 

