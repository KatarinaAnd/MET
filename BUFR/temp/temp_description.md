# temp
#### parse_arguments()

reads arguments parsed from terminal. Takes in following arguements:
* -c, --cfg: the path + name of configuration file
* -s, --startday: if the user wants to extract data from a specific time interval, add startday and endday. If hour not specified, default start will be first data registered from 00:00 for that day.
* -e, --endday: If hour not specified, default end will be last data registered up until 23:59.
* -t, --type: Must specify type of station to extract data from. Can choose between "block" (stations registered with  blockNumber and stateIdentifier), "wigos" (stations registered with wigosNumbers) or "radio" (radiosondes).
* -i, --init: reads all the files from the folder containing the bufr files.
* -u, --update: reads the files from output folder to find the last date to update from. Goes to the folder containing bufr files and collects data from said date.
* -a, --all: extracts data from all available stations
* -st, --station: extracts data from specified station. Must be in the from "st1 st2 .. stn". If the stationtype, t = block, the stations have to be specified through "[blockNumber][stationNumber]". If t = wigos the stations have to be specified as "[wigosIdentifierSeries]-[wigosIssuerOfIdentifier]-[wigosIssueNumber]-[wigosLocalIdentifierCharacter]", and if t = radio the stations must be specified as "[radiosondeSerialNumber]"
