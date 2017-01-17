@if "%DEBUG%" == "" @echo off
@rem ##########################################################################
@rem
@rem  hello-kafka-streams startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

@rem Add default JVM options here. You can also use JAVA_OPTS and HELLO_KAFKA_STREAMS_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS=

set DIRNAME=%~dp0
if "%DIRNAME%" == "" set DIRNAME=.
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%..

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if "%ERRORLEVEL%" == "0" goto init

echo.
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto init

echo.
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME%
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:init
@rem Get command-line arguments, handling Windowz variants

if not "%OS%" == "Windows_NT" goto win9xME_args
if "%@eval[2+2]" == "4" goto 4NT_args

:win9xME_args
@rem Slurp the command line arguments.
set CMD_LINE_ARGS=
set _SKIP=2

:win9xME_args_slurp
if "x%~1" == "x" goto execute

set CMD_LINE_ARGS=%*
goto execute

:4NT_args
@rem Get arguments from the 4NT Shell from JP Software
set CMD_LINE_ARGS=%$

:execute
@rem Setup the command line

set CLASSPATH=%APP_HOME%\lib\hello-kafka-streams-0.10.0.0.jar;%APP_HOME%\lib\connect-runtime-0.10.0.0.jar;%APP_HOME%\lib\connect-api-0.10.0.0.jar;%APP_HOME%\lib\kafka-streams-0.10.0.0.jar;%APP_HOME%\lib\irclib-1.10.jar;%APP_HOME%\lib\reflections-0.9.10.jar;%APP_HOME%\lib\kafka-clients-0.10.0.0.jar;%APP_HOME%\lib\jackson-jaxrs-json-provider-2.6.3.jar;%APP_HOME%\lib\jersey-container-servlet-2.22.2.jar;%APP_HOME%\lib\kafka-tools-0.10.0.0.jar;%APP_HOME%\lib\jetty-servlet-9.2.15.v20160210.jar;%APP_HOME%\lib\jetty-servlets-9.2.15.v20160210.jar;%APP_HOME%\lib\jetty-server-9.2.15.v20160210.jar;%APP_HOME%\lib\zkclient-0.8.jar;%APP_HOME%\lib\connect-json-0.10.0.0.jar;%APP_HOME%\lib\rocksdbjni-4.4.1.jar;%APP_HOME%\lib\jackson-databind-2.6.3.jar;%APP_HOME%\lib\guava-18.0.jar;%APP_HOME%\lib\javassist-3.18.2-GA.jar;%APP_HOME%\lib\lz4-1.3.0.jar;%APP_HOME%\lib\snappy-java-1.1.2.4.jar;%APP_HOME%\lib\jackson-jaxrs-base-2.6.3.jar;%APP_HOME%\lib\jackson-core-2.6.3.jar;%APP_HOME%\lib\jackson-module-jaxb-annotations-2.6.3.jar;%APP_HOME%\lib\jersey-container-servlet-core-2.22.2.jar;%APP_HOME%\lib\jersey-common-2.22.2.jar;%APP_HOME%\lib\jersey-server-2.22.2.jar;%APP_HOME%\lib\javax.ws.rs-api-2.0.1.jar;%APP_HOME%\lib\argparse4j-0.5.0.jar;%APP_HOME%\lib\kafka-log4j-appender-0.10.0.0.jar;%APP_HOME%\lib\jetty-security-9.2.15.v20160210.jar;%APP_HOME%\lib\jetty-continuation-9.2.15.v20160210.jar;%APP_HOME%\lib\jetty-http-9.2.15.v20160210.jar;%APP_HOME%\lib\jetty-util-9.2.15.v20160210.jar;%APP_HOME%\lib\jetty-io-9.2.15.v20160210.jar;%APP_HOME%\lib\javax.servlet-api-3.1.0.jar;%APP_HOME%\lib\zookeeper-3.4.6.jar;%APP_HOME%\lib\jackson-annotations-2.6.0.jar;%APP_HOME%\lib\javax.inject-2.4.0-b34.jar;%APP_HOME%\lib\javax.annotation-api-1.2.jar;%APP_HOME%\lib\jersey-guava-2.22.2.jar;%APP_HOME%\lib\hk2-api-2.4.0-b34.jar;%APP_HOME%\lib\hk2-locator-2.4.0-b34.jar;%APP_HOME%\lib\osgi-resource-locator-1.0.1.jar;%APP_HOME%\lib\jersey-client-2.22.2.jar;%APP_HOME%\lib\jersey-media-jaxb-2.22.2.jar;%APP_HOME%\lib\validation-api-1.1.0.Final.jar;%APP_HOME%\lib\jline-0.9.94.jar;%APP_HOME%\lib\netty-3.7.0.Final.jar;%APP_HOME%\lib\hk2-utils-2.4.0-b34.jar;%APP_HOME%\lib\aopalliance-repackaged-2.4.0-b34.jar;%APP_HOME%\lib\junit-3.8.1.jar;%APP_HOME%\lib\javax.inject-1.jar;%APP_HOME%\lib\slf4j-api-1.7.21.jar;%APP_HOME%\lib\slf4j-log4j12-1.7.21.jar;%APP_HOME%\lib\log4j-1.2.17.jar

@rem Execute hello-kafka-streams
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %HELLO_KAFKA_STREAMS_OPTS%  -classpath "%CLASSPATH%" io.amient.examples.wikipedia.WikipediaStreamDemo %CMD_LINE_ARGS%

:end
@rem End local scope for the variables with windows NT shell
if "%ERRORLEVEL%"=="0" goto mainEnd

:fail
rem Set variable HELLO_KAFKA_STREAMS_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
if  not "" == "%HELLO_KAFKA_STREAMS_EXIT_CONSOLE%" exit 1
exit /b 1

:mainEnd
if "%OS%"=="Windows_NT" endlocal

:omega
