import json
import pandas as pd
import xarray as xr
import yaml
import time
from itertools import dropwhile
import sys 
import os
import subprocess
from eccodes import *
import requests
import argparse
from io import StringIO
import logging
from logging.handlers import TimedRotatingFileHandler
import numpy as np
import traceback
from SPARQLWrapper import SPARQLWrapper, JSON
import operator
import re
from dateutil.relativedelta import relativedelta
sys.path.append('/home/katarinana/work_desk/BUFR/funcs') #path to code_tables.py, get_keywords.py and useful_functions.py 
from get_keywords import get_keywords
from code_tables import *
from useful_functions import *
import glob
from datetime import datetime, timedelta, date
from calendar import monthrange, month_name

def parse_arguments():

    # reads arguments parsed from terminal

    parser = argparse.ArgumentParser()
    
    parser.add_argument("-c","--cfg",dest="cfgfile",
            help="Configuration file", required=True)
    parser.add_argument("-s","--startday",dest="startday",
            help="Start day in the form YYYY-MM-DD", required=False)
    parser.add_argument("-e","--endday",dest="endday",
            help="End day in the form YYYY-MM-DD", required=False)
    parser.add_argument("-t","--type",dest="stationtype",
            help="Choose between block, wigos or radio", required=True)
    parser.add_argument("-i", "--init", dest="initialize",
            help="Download all data", required=False, action="store_true")
    parser.add_argument("-u", "--update", dest="update",
            help="Adds the latest bufr-data to the netcdf-file", required=False, action="store_true")
    parser.add_argument("-a", "--all", dest="all_stations",
            help="To download/upload data from all stations", required=False, action="store_true")
    parser.add_argument("-st", "--station", nargs='*', default=[], dest="spec_station",
            help='To select specific stations. Must be in the from "st1 st2 .. stn". Must not be separated by comma', required=False)
    args = parser.parse_args()

    if args.startday is None:
        pass
    else:
        try:
            datetime.strptime(args.startday,'%Y-%m-%d')
        except ValueError:
            raise ValueError
        
    if args.endday is None:
            pass
    else:
        try:
            datetime.strptime(args.endday,'%Y-%m-%d')
        except ValueError:
            raise ValueError
        
    if args.cfgfile is None:
        parser.print_help()
        parser.exit()
        
    if args.stationtype is None:
        parser.print_help()
        parser.exit
    return args

def parse_cfg(cfgfile):
    
    # reads the configuration file
    
    with open(cfgfile, 'r') as ymlfile:
        cfgstr = yaml.full_load(ymlfile)
    return cfgstr

def get_files_specified_dates(desired_path):
    
    # if the user wants to extract data from specific dates, this function will run.
    # it opens up the file folder, checks the date from the parser input and returns a list of
    # files that contains data from within the timeinterval given. 
    
    get_args = parse_arguments()

        
    path = parse_cfg(get_args.cfgfile)['station_info']['path']

    # open up path to files and sort the files such that the date is in chronological order
    files = []
    for file in os.listdir(desired_path):
        if file.endswith('.bufr'):
            files.append(datetime.strptime(file[5:-5], "%Y%m%d%H"))
    
    files = sorted(files)
    sorted_files = []
    for i in files:
        sorted_files.append(path + "/temp_" + datetime.strftime(i, "%Y%m%d%H") + '.bufr')
    
    # get startday from parser
    if get_args.startday and get_args.endday:
        start = get_args.startday
        end = get_args.endday
    else:
        start = str(date.today())
        end = str(date.today())
        print(start)
    
    start = start.replace('-','')
    end = end.replace('-','')
    
    startday = []       
    endday = [] 
    for i in sorted_files:
        if start in i:
            startday.append(i) 
        if end in i:
            endday.append(i)
            
    if len(startday) == 0:
        print('your startdate is out of range')
        sys.exit()
    if len(endday) == 0:
        print('your endday is out of range')
        sys.exit()
        
    startpoint_index = sorted_files.index(startday[0])
    endpoint_index = sorted_files.index(endday[-1]) + 1
    
    return sorted_files[startpoint_index:endpoint_index]


def get_files_initialize(desired_path):
    
    # gets a list of the files that we wish to look at

    files = []
    for file in os.listdir(desired_path):
        if file.endswith('.bufr'):
          # Create the filepath of particular file
            file_path = ('{}/{}'.format(desired_path,file))
            files.append(file_path)
    return files

    
def bufr_2_json(file):
    
    #open bufr file, convert to json (using "-j s") and load it with json.loads

    json_file = json.loads(subprocess.check_output("bufr_dump -j f {}".format(file), shell=True))
    
    # sorting so that each subset is a list of dictionary
    count = 0
    sorted_messages = []
    for message in json_file['messages']:
        if message['key'] == 'subsetNumber':
            count += 1
            sorted_messages.append([])
        else:
            try:
                sorted_messages[count-1].append({'key': message['key'], 'value': message['value'],
                                   'code': message['code'], 'units': message['units']})
            except:
                continue
    
    # sorting so that height of measurement equipment is a variable attribute instead of variabl
    
        
    finale= []
    for msg in sorted_messages:
        time_code = ['004024', '004025']
        count_time = 0
        variables_with_time = []
        storing_time = []
        for i in msg:
            if i['code'] in time_code and i['value'] != None:
                count_time += 1
                storing_time.append(i)
            if i['code'] in time_code and i['value'] == None:
                count_time += 1
                storing_time.append(None)
            if count_time == 0:
                variables_with_time.append(i)
            if count_time != 0 and i['code'] not in time_code:
                if storing_time[count_time-1] != None:
                    i['time'] = storing_time[count_time-1]
                variables_with_time.append(i)
        finale.append(variables_with_time) 
    return finale


def return_list_of_stations(get_files):
    cfg = parse_cfg(parse_arguments().cfgfile)
    stationtype = parse_arguments().stationtype
    stations = []
    if stationtype == 'block':
        for one_file in get_files:
            simple_file = bufr_2_json(one_file)
            for station in simple_file:
                if station[0]['key'] == 'blockNumber' and station[1]['key'] == 'stationNumber':
                    station_num =  str(station[0]['value']).zfill(2) + str(station[1]['value']).zfill(3)
                    if station_num not in stations and station_num != 'NoneNone':
                        stations.append(station_num)
    if stationtype == 'wigos':
        for one_file in get_files:
            simple_file = bufr_2_json(one_file)
            for station in simple_file:
                if station[0]['key'] == 'wigosIdentifierSeries' and station[1]['key'] == 'wigosIssuerOfIdentifier' and station[2]['key'] == 'wigosIssueNumber' and station[3]['key'] == 'wigosLocalIdentifierCharacter':
                    station_num =  str(station[0]['value']) + '-' + str(station[1]['value']) + '-' + str(station[2]['value']) + '-' + str(station[3]['value'])
                    if station_num not in stations and station_num != 'None-None-None-None':
                        stations.append(station_num)
    if stationtype == 'radio':
        for one_file in get_files:
            simple_file = bufr_2_json(one_file)
            for station in simple_file:
                if station[0]['key'] == 'radiosondeSerialNumber':
                    station_num = str(station[0]['value'])
                    if station_num not in stations and station_num != 'None':
                        stations.append(station_num)
    
    return stations


def sorting_hat(get_files, stations = 1):
    cfg = parse_cfg(parse_arguments().cfgfile)
    
    if not parse_arguments().spec_station and stations == 1:
        stations = return_list_of_stations(get_files)
    elif parse_arguments().spec_station and stations == 1:
        stations = parse_arguments().spec_station
        
    stations_dict = {i : [] for i in stations}
    
    for one_file in get_files:
        simple_file = bufr_2_json(one_file)
        for station in simple_file:
            if parse_arguments().stationtype == 'block':
                if str(station[0]['value']).zfill(2) + str(station[1]['value']).zfill(3) in stations:
                    stations_dict['{}'.format(str(station[0]['value']).zfill(2) + str(station[1]['value']).zfill(3))].append(station)
            elif parse_arguments().stationtype == 'wigos':
                if str(station[0]['value']) + '-' + str(station[1]['value']) + '-' + str(station[2]['value']) + '-' + str(station[3]['value']) in stations:
                    stations_dict['{}'.format(str(station[0]['value']) + '-' + str(station[1]['value']) + '-' + str(station[2]['value']) + '-' + str(station[3]['value']))].append(station)
            elif parse_arguments().stationtype == 'radio':
                if str(station[0]['value']) in stations:
                    stations_dict['{}'.format(str(station[0]['value']))].append(station)
    
    print('bufr successfully converted to json')
    print('sorting hat completed')
    
    return stations_dict


    
def json_to_ds(msg):
    dfs = []
    
    check_list = ['pressure', 'verticalSoundingSignificance', 'nonCoordinateGeopotential',
                  'airTemperature', 'dewpointTemperature', 'windDirection', 'windSpeed']
    
    xars = []
    pressure_ds = []
    other_ds = []
    df_units = []
    
    
    for i in msg:
        count1 = 0
        count2 = 0
   
        pressure = []
        other = []
        for_units = []
     
        for j in i:    
            for_units.append({j['key']: {'units':j['units'], 'code':j['code']}})
            if j['key'] == 'pressure':
                count1 += 1
                pressure.append({'{}'.format(j['value']):[]})
            elif count1 != 0 and j['key'] in check_list:
                pressure[count1-1]['{}'.format(str(pressure[count1-1].keys())[12:-3])].append(j)
            else:
                other.append(j)
        
        df = pd.DataFrame(filter_section(other))
        
        # need to filter of some more 
        df = df[['key','value','units','code']].copy()
        
        df_vals = df[['key','value']].copy()
        
        df_vals = df_vals.transpose()
        df_vals = df_vals.reset_index()
        df_vals = df_vals.rename(columns=df_vals.iloc[0])
        df_vals = df_vals.drop(df.index[0])
        
        try:
            blob = (str(int(df_vals['year'][1])).zfill(4) + '-' + str(int(df_vals['month'][1])).zfill(2) + '-' + str(int(df_vals['day'][1])).zfill(2) + ' ' + str(int(df_vals['hour'][1])).zfill(2) + ':' +  str(int(df_vals['minute'][1])).zfill(2) + ':' + str(int(df_vals['second'][1])).zfill(2))
            blob = datetime.strptime(blob, "%Y-%m-%d %H:%M:%S")
            df_vals['time'] = blob
            df_vals = df_vals.drop(columns = ['key','year', 'month', 'day','hour', 'minute', 'second'])
        except:
            blob = (str(int(df_vals['year'][1])).zfill(4) + '-' + str(int(df_vals['month'][1])).zfill(2) + '-' + str(int(df_vals['day'][1])).zfill(2) + ' ' + str(int(df_vals['hour'][1])).zfill(2) + ':' +  str(int(df_vals['minute'][1])).zfill(2))
            blob = datetime.strptime(blob, "%Y-%m-%d %H:%M")
            df_vals['time'] = blob
            df_vals = df_vals.drop(columns = ['key','year', 'month', 'day','hour', 'minute'])
        
        
        for k in pressure:
            for l in k:
                
                tiny_df = pd.DataFrame.from_dict(k[l])
                tiny_df = tiny_df[['key','value']].copy().transpose().reset_index().drop(columns=['index'])
                header = tiny_df.iloc[0]
                tiny_df = tiny_df[1:]
                tiny_df.columns = header
                tiny_df['pressure'] = list(k.keys())[0]
                tiny_df['index'] = count2
                tiny_df = tiny_df.set_index('index')
                
                vars_we_dont_want = search_func(['dataPresentIndicator','centre', 
                                                 'generatingApplication','extendedDelayedDescriptorReplicationFactor',
                                                'delayedDescriptorReplicationFactor'], 
                                                list(tiny_df))
                tiny_df = tiny_df.drop(columns=vars_we_dont_want)
                dfs.append(tiny_df)
                count2 += 1
        try:
            if len(dfs) > 1:        
                big_df = pd.concat(dfs[:-1], ignore_index=True)
            elif len(dfs) == 1:
                big_df = dfs[0]
            else:
                print('could not extract data')
                return
        except:
            for i in dfs:
                print(i.columns)

        
        
        for column in big_df.columns:
            try:
                big_df[column] = pd.to_numeric(big_df[column])
            except:
                big_df[column] = big_df[column]
                
        big_df = big_df.reset_index()
        big_df = big_df[big_df.pressure != 'None']
        big_df['time'] = [blob for i in range(len(big_df['{}'.format(big_df.columns[0])]))]
        big_df = big_df.set_index(['time','pressure'])
        big_df = big_df.drop(columns=['index'])
        big_df = big_df[~big_df.index.duplicated()]
        big_df = big_df.fillna(-9999)
        pressure_ds.append(big_df)
                
        df_vals = df_vals.set_index('time')
        cols = pd.io.parsers.base_parser.ParserBase({'names':df_vals.columns, 'usecols':None})._maybe_dedup_names(df_vals.columns)
        
        df_vals.columns = cols # will add a ".1",".2" etc for each double name
        for column in df_vals.columns:
            try:
                df_vals[column] = pd.to_numeric(df_vals[column])
            except:
                df_vals[column] = df_vals[column]
        df_vals = df_vals.fillna(-9999)
        other_ds.append(df_vals)
        
        units_df = pd.DataFrame(for_units)

        new_unit = pd.DataFrame()
        for i in units_df.columns:
            try:
                vals = units_df[i].loc[~units_df[i].isnull()].iloc[0]
                new_unit.at['units','{}'.format(i)] = vals['units']
                new_unit.at['code','{}'.format(i)] = vals['code']

            except:
                continue
        new_unit = new_unit.transpose()
        new_unit = new_unit.reset_index().rename(columns={'index':'key'})
        cols = pd.io.parsers.base_parser.ParserBase({'names':new_unit['key'], 'usecols':None})._maybe_dedup_names(new_unit['key'])
        new_unit['key'] = cols # will add a ".1",".2" etc for each double name
        df_units.append(new_unit)
    
    
    
    if len(pressure_ds) > 1:
        tik = pd.concat(pressure_ds)
    elif len(pressure_ds) == 1:
        tik = pressure_ds[0]
    else:
        message = ('no data')
        return message
    
    if len(other_ds) > 1:
        tak = pd.concat(other_ds)
    elif len(other_ds) == 1:
        tak = other_ds[0]
    else:
        message = ('no data')
        return message
    
    
    if units_df.empty:
        units_df= pd.DataFrame({'key': ['something','to','make', 'it' ,'pass']})
    else:
        units_df = units(df_units)
    
    ds_station1 = tik.to_xarray()
    ds_station2 = tak.to_xarray()
   
    main_ds = xr.combine_by_coords([ds_station1, ds_station2])

    print(main_ds)
    # some variables only need the first value as they are not dependent on time
    vars_one_val = ['blockNumber', 'stationNumber','latitude',
                    'longitude', 'heightOfStation', 'wigosIdentifierSeries', 'wigosIssuerOfIdentifier',
                    'wigosIssueNumber','wigosLocalIdentifierCharacter']
    for i in main_ds.keys():
        if i in vars_one_val:
            main_ds[i] = main_ds[i].isel(time=0)
    
    to_get_keywords = []
    #print(main_ds.keys())
    for variable in main_ds.keys():
        #print('var : ', variable)
        kokko = variable
        var = variable
        if variable[-2] == '.':
            var = variable[:-2]
        change_upper_case = re.sub('(?<!^)(?=\d{2})', '_',re.sub('(?<!^)(?=[A-Z])', '_', var)).lower()
        
        # checking for standardname
        standardname_check = cf_match(change_upper_case)
        if standardname_check != 'fail':
            main_ds[variable].attrs['standard_name'] = standardname_check
        manual_stdname = {'windDirection': 'wind_from_direction', 'dewpointTemperature': 'dew_point_temperature',
                         'heightOfBaseOfCloud':'cloud_base_altitude'}
        if var in manual_stdname.keys():
            main_ds[variable].attrs['standard_name'] = manual_stdname[var]
        #print('kokko1: ',kokko)
        # adding long name. if variable has a height attribute, add it in the long name. if variable has a time attribute, add it in the long name.
        long_name = re.sub('_',' ', change_upper_case)
        main_ds[variable].attrs['long_name'] = long_name
        
        # adding units, if units is a CODE TABLE or FLAG TABLE, it will overrule the previous set attributes to set new ones
        if var in list(units_df['key']):
            main_ds[variable].attrs['units'] = units_df.loc[units_df['key'] == var, 'units'].iloc[0]
        else:
            continue
        
        if main_ds[variable].attrs['units'] == 'deg' and variable not in ['longitude', 'latitude']:
            main_ds[variable].attrs['units'] = 'degrees'
        elif variable == 'latitude' and main_ds[variable].attrs['units'] == 'deg':
            main_ds[variable].attrs['units'] = 'degrees_north'
        elif variable == 'longitude' and main_ds[variable].attrs['units'] == 'deg':
            main_ds[variable].attrs['units'] = 'degrees_east'
        elif main_ds[variable].attrs['units'] == 'Numeric':
            main_ds[variable].attrs['units'] = '1'
        elif main_ds[variable].attrs['units'] == 'CODE TABLE':
            main_ds[variable].attrs['long_name'] = main_ds[variable].attrs['long_name'] + ' according to WMO code table ' + units_df.loc[units_df['key'] == var, 'code'].iloc[0]  
            main_ds[variable].attrs['units'] = '1'
        elif main_ds[variable].attrs['units'] == 'FLAG TABLE':
            main_ds[variable].attrs['long_name'] = main_ds[variable].attrs['long_name'] + ' according to WMO flag table ' + units_df.loc[units_df['key'] == var, 'code'].iloc[0]
            main_ds[variable].attrs['units'] = '1'
        
        # adding coverage_content_type
        thematicClassification = ['blockNumber', 'stationNumber', 'stationType', 'wigosIdentifierSeries', 
                                  'wigosIssuerOfIdentifier', 'wigosIssueNumber','wigosLocalIdentifierCharacter']
        if variable in thematicClassification:
            main_ds[variable].attrs['coverage_content_type'] = 'thematicClassification'
        elif variable in ['longitude', 'latitude', 'time']:
            main_ds[variable].attrs['coverage_content_type'] = 'referenceInformation'
        else:
            main_ds[variable].attrs['coverage_content_type'] = 'physicalMeasurement'
        
        
        if variable[-2] == '.':
            new_name = variable.replace('.', '')
            main_ds[new_name] = main_ds[variable]
            main_ds = main_ds.drop([variable])
            
        to_get_keywords.append(change_upper_case)
        
        # must rename if variable name starts with a digit
        timeunits = ['hour', 'second', 'minute', 'year', 'month', 'day']
        if change_upper_case[0].isdigit() == True and change_upper_case.split('_')[1].lower() in timeunits:
            fixing_varname = re.sub( r"([A-Z])", r" \1", variable).split()
            fixing_varname = fixing_varname[2:] + fixing_varname[:2] + ['s']
            fixing_varname = ''.join(fixing_varname)
            fixing_varname = fixing_varname[0].lower() + fixing_varname[1:]
            main_ds[fixing_varname] = main_ds[variable]
            main_ds = main_ds.drop([variable])
        

    #### GLOBAL ATTRIBUTES #####
    ################# REQUIRED GLOBAL ATTRIBUTES ###################
    # this probably might have to be modified
    keywords, keywords_voc = get_keywords(to_get_keywords)
    cfg = parse_cfg(parse_arguments().cfgfile)
    main_ds.attrs['featureType'] = 'profile'
    main_ds.attrs['naming_authority'] = 'World Meteorological Organization (WMO)'
    main_ds.attrs['source'] = cfg['output']['source']
    main_ds.attrs['summary'] = cfg['output']['abstract']
    today = date.today()
    main_ds.attrs['history'] = today.strftime('%Y-%m-%d %H:%M:%S')+': Data converted from BUFR to NetCDF-CF'
    main_ds.attrs['date_created'] = today.strftime('%Y-%m-%d %H:%M:%S')
    main_ds.attrs['geospatial_lat_min'] = '{:.3f}'.format(main_ds['latitude'].values.min())
    main_ds.attrs['geospatial_lat_max'] = '{:.3f}'.format(main_ds['latitude'].values.max())
    main_ds.attrs['geospatial_lon_min'] = '{:.3f}'.format(main_ds['longitude'].values.min())
    main_ds.attrs['geospatial_lon_max'] = '{:.3f}'.format(main_ds['longitude'].values.max())
    main_ds.attrs['time_coverage_start'] = main_ds['time'].values[0].astype('datetime64[s]').astype(datetime).strftime('%Y-%m-%d %H:%M:%S') # note that the datetime is changed to microsecond precision from nanosecon precision
    main_ds.attrs['time_coverage_end'] = main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime).strftime('%Y-%m-%d %H:%M:%S')
    
    duration_years = str(relativedelta(main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime), main_ds['time'].values[0].astype('datetime64[s]').astype(datetime)).years)
    duration_months = str(relativedelta(main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime), main_ds['time'].values[0].astype('datetime64[s]').astype(datetime)).months)
    duration_days = str(relativedelta(main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime), main_ds['time'].values[0].astype('datetime64[s]').astype(datetime)).days)
    duration_hours = str(relativedelta(main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime), main_ds['time'].values[0].astype('datetime64[s]').astype(datetime)).hours)
    duration_minutes = str(relativedelta(main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime), main_ds['time'].values[0].astype('datetime64[s]').astype(datetime)).minutes)
    duration_seconds = str(relativedelta(main_ds['time'].values[-1].astype('datetime64[s]').astype(datetime), main_ds['time'].values[0].astype('datetime64[s]').astype(datetime)).seconds)
    main_ds.attrs['time_coverage_duration'] = ('P' + duration_years + 'Y' + duration_months +
                                               'M' + duration_days + 'DT' + duration_hours + 
                                               'H' + duration_minutes + 'M' + duration_seconds + 'S')    
    
    main_ds.attrs['keywords'] = keywords
    main_ds.attrs['keywords_vocabulary'] = keywords_voc
    main_ds.attrs['standard_name_vocabulary'] = 'CF Standard Name V79'
    main_ds.attrs['Conventions'] = 'ACDD-1.3, CF-1.6'
    main_ds.attrs['creator_type'] = cfg['author']['creator_type']
    main_ds.attrs['institution'] = cfg['author']['PrincipalInvestigatorOrganisation']
    main_ds.attrs['creator_name'] = cfg['author']['PrincipalInvestigator']
    main_ds.attrs['creator_email'] = cfg['author']['PrincipalInvestigatorEmail']
    main_ds.attrs['creator_url'] = cfg['author']['PrincipalInvestigatorOrganisationURL']
    main_ds.attrs['publisher_name'] = cfg['author']['Publisher']
    main_ds.attrs['publisher_email'] = cfg['author']['PublisherEmail']
    main_ds.attrs['publisher_url'] = cfg['author']['PublisherURL']
    main_ds.attrs['project'] = cfg['author']['Project']
    main_ds.attrs['license'] = cfg['author']['License']
    
    return main_ds
    

def set_encoding(ds, fill=-9999, time_name = 'time', time_units='seconds since 1970-01-01 00:00:00'):
    
    all_encode = {}
    liste = list(ds.keys())
    for v in liste:
        #if v == 'softwareVersionNumber':
         #   encode = {'zlib': True, 'complevel': 9, '_FillValue':fill}
        print(v)
        if v == 'time':
            dtip = 'i4'
        elif 'float' in str(ds[v].dtype):
            dtip = 'f4'
        elif 'int' in str(ds[v].dtype):
            dtip = 'i4'
        encode = {'zlib': True, 'complevel': 9, 'dtype': dtip, '_FillValue':fill}

            
        all_encode[v] = encode

    return all_encode

def saving_grace(file, key, destdir):
    file = file.sortby('time')
    gb = file.groupby('time.month')
    
        
    #gb = gb.sortby('time')
    print(file.time.values[0])
    print(type(file.time.values[0]))
    for group_name, group_da in gb:
        #group_da = file
        t1 = group_da.time.isel(time=0).values.astype('datetime64[s]')
        t1 = t1.astype(datetime)
        t2 = group_da.time.isel(time=-1).values.astype('datetime64[s]')
        t2 = t2.astype(datetime)


        timestring1 = t1.strftime('%Y%m%dT%H%M%S')
        timestring2 = t2.strftime('%Y%m%dT%H%M%S')

        group_da['time'].attrs['units'] = "seconds since 1970-01-01 00:00:00"
        group_da['time'].attrs['standard_name'] = 'time'
        group_da['time'].attrs['long_name'] = 'time'
        group_da['time'].attrs['coverage_content_type'] = 'referenceInformation'
        
        group_da['pressure'].attrs['units'] = "hPa"
        group_da['pressure'].attrs['standard_name'] = 'air_pressure'
        group_da['pressure'].attrs['long_name'] = 'air_pressure'
        group_da['pressure'].attrs['coverage_content_type'] = 'referenceInformation'
        
        group_da.attrs['id'] = 'temp_{}_{}-{}.nc'.format(key, timestring1, timestring2)
        group_da.attrs['title'] = 'Measurements from station with station identifier number {}'.format(key)

        ds_dictio = group_da.to_dict()

        bad_time = ds_dictio['coords']['time']['data']
        ds_dictio['coords']['time']['data'] = np.array([((ti - datetime(1970,1,1)).total_seconds()) for ti in bad_time]).astype('i4')
        print(ds_dictio['coords']['time'])
        ds_dictio['coords']['pressure']['data'] = np.float32(ds_dictio['coords']['pressure']['data'])
        all_ds_station_period = xr.Dataset.from_dict(ds_dictio)
        print(all_ds_station_period['time'])
        all_ds_station_period.to_netcdf('{}/temp_{}_{}-{}.nc'.format(destdir, key, timestring1, timestring2), encoding=set_encoding(all_ds_station_period, time_units='seconds since 1970-01-01 00:00:00'))

            
if __name__ == "__main__":
    parse = parse_arguments()
    
    cfg = parse_cfg(parse.cfgfile)
    destdir = cfg['output']['destdir']
    frompath = cfg['station_info']['path']
    stationtype = parse.stationtype
    
    if parse.initialize:
        print('initialization has begun')
        sorted_files = sorting_hat(get_files_initialize(frompath))
        for key, val in sorted_files.items():
            file = json_to_ds(sorted_files['{}'.format(key)])
            #file.to_netcdf('test1.nc')
            #sys.exit()
            saving = saving_grace(file, key, destdir)
        
               
    elif parse.update:
        print('updating...')
        
        # find the latest date that is stored in the folder
        
        stations = {}
        stations_names = []
        #print(stations_names)
        # get list of stationname in folder

        for file in os.listdir(destdir):
            if file.endswith('.nc'):
                file_split = file.split('_')
                if parse.stationtype == 'block':
                    #print(len(file_split[1]))
                    #sys.exit()
                    if len(file_split[1]) == 5:
                        if file_split[1] not in stations_names:
                            stations[file_split[1]] = [[file_split[2].split('-')[0], file_split[2].split('-')[1][:-3]]]
                            stations_names.append(file_split[1])
                        else:
                            stations[file_split[1]].append([file_split[2].split('-')[0], file_split[2].split('-')[1][:-3]])
                    else:
                        continue
                        
                elif parse.stationtype == 'wigos':
                    if '-' in file_split[1]:
                        if file_split[1] not in stations_names:
                            stations[file_split[1]] = [[file_split[2].split('-')[0], file_split[2].split('-')[1][:-3]]]
                            stations_names.append(file_split[1])
                        else:
                            stations[file_split[1]].append([file_split[2].split('-')[0], file_split[2].split('-')[1][:-3]])
                        
                    else:
                        continue
                        
                elif parse.stationtype == 'radio':
                    if len(file_split[1])>5 and '-' not in file_split[1]:
                        if file_split[1] not in stations_names:
                            stations[file_split[1]] = [[file_split[2].split('-')[0], file_split[2].split('-')[1][:-3]]]
                            stations_names.append(file_split[1])
                        else:
                            stations[file_split[1]].append([file_split[2].split('-')[0], file_split[2].split('-')[1][:-3]])
                    else:
                        continue
                else:
                    print('must specify stationtype')
                    sys.exit()
        if parse.all_stations == True:            
            all_files = (return_list_of_stations(get_files_specified_dates(parse_cfg(parse.cfgfile)['station_info']['path'])))
        elif parse.spec_station:
            all_files = parse.spec_station
            

        for i in all_files:
            if i in stations_names:
                sorted_files = sorting_hat(get_files_specified_dates(parse_cfg(parse.cfgfile)['station_info']['path']), stations = [str(i)])
                
                file = json_to_ds(sorted_files['{}'.format(i)])
                
                # figuring out which is the last file for that station
                
                end_dates = []
                for k in stations[i]:
                    end_dates.append(datetime.strptime(k[1],'%Y%m%dT%H%M%S'))
                
                last_date = max(end_dates).strftime('%Y%m%dT%H%M%S')
                
                for k in stations[i]:
                    if last_date in k:
                        startday, endday = k
                
                #open latest dataset
                last_file = xr.open_dataset("{}/temp_{}_{}-{}.nc".format(destdir, i, startday, endday),decode_times=False)
                
                # must fix decoding thingy and name of dims in order to merge datasets together
                last_file_time = last_file.drop_dims('obs')
                last_file_pressure = last_file.drop_dims('profile')
                
                file_time = file.drop_dims('pressure')
                file_pressure = file.drop_dims('time')
                
                
                file_time = file_time.rename_dims({'time': 'profile'})
                file_pressure = file_pressure.rename_dims({'pressure': 'obs'})
                
                #rearrange dims for prof
                time = file_time.to_pandas()
                time['time'] = [to_datetime(ti) for ti in time['time']]
                
                last_file_time = last_file_time.to_pandas()
                last_file_time['time'] = [datetime.fromtimestamp(ti) for ti in last_file_time['time']]
                
                # making sure that the datasets have the same columns
                for o in list(time.columns):
                    if o not in list(last_file_time.columns):
                        time[o] = list(np.empty(len(time.index)))
                for o in list(last_file_time.columns):
                    if o not in list(time.columns):
                        last_file_time[o] = list(np.empty(len(last_file_time.index)))
                
                
                new_file_prof = pd.concat([time, last_file_time])
                new_file_prof = new_file_prof.sort_values(by=['time'])
                new_file_prof = new_file_prof.set_index('time')
                new_file_prof = xr.Dataset.from_dataframe(new_file_prof)
                
                #rearrange dims for obs
                pressure = file_pressure.to_pandas()
                last_file_pressure = last_file_pressure.to_pandas()
                
                for o in list(pressure.columns):
                    if o not in list(last_file_pressure.columns):
                        pressure[o] = list(np.empty(len(pressure.index)))
                for o in list(last_file_pressure.columns):
                    if o not in list(pressure.columns):
                        last_file_pressure[o] = list(np.empty(len(last_file_pressure.index)))
        
                new_file_obs = pd.concat([pressure, last_file_pressure])
                new_file_obs = new_file_obs.set_index('pressure')
                new_file_obs = xr.Dataset.from_dataframe(new_file_obs)
        
                # merging
                new_file = xr.merge([new_file_prof, new_file_obs],compat ='override')
        
                #finally remove the old file from destdir and save the new one
                last_file.close()
                os.remove("{}/temp_{}_{}-{}.nc".format(destdir, i, startday, endday))
                
                #lastly save
                saving = saving_grace(new_file, i, destdir)
                
            else:
                continue

                
    elif parse.startday != None:
        print('creating files from {}'.format(parse.startday))
        
        sorted_files = sorting_hat(get_files_specified_dates(frompath))
        #print(sorted_files.keys)
        for key,val in sorted_files.items():
            file = json_to_ds(sorted_files['{}'.format(key)])
            saving = saving_grace(file, key, destdir)
            #print(file)
            #sys.exit()
        
    else:
        print('either type in -i, -u or enter starday/endday')
        sys.exit()
        
 