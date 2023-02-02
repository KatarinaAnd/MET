import json
from unittest.mock import NonCallableMock
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
import matplotlib.pyplot as plt
import numpy as np
import traceback
from SPARQLWrapper import SPARQLWrapper, JSON
import operator
import re
from dateutil.relativedelta import relativedelta
sys.path.append('/home/katarinana/work_desk/BUFR/funcs')
from get_keywords import get_keywords
from code_tables import *
from useful_functions import *
import netCDF4
import glob
from datetime import datetime, timedelta, date
from calendar import monthrange, month_name

def parse_arguments():
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
        
    return args

def parse_cfg(cfgfile):

    with open(cfgfile, 'r') as ymlfile:
        cfgstr = yaml.full_load(ymlfile)
    return cfgstr

def get_files_specified_dates(desired_path):
    
    get_args = parse_arguments()
    startday = get_args.startday
    endday = get_args.endday
    path = parse_cfg(get_args.cfgfile)['station_info']['path']

    # open up path to files and sort the files such that the date is in chronological order
    files = []
    for file in os.listdir(desired_path):
        if file.endswith('.bufr'):
            files.append(datetime.strptime(file[5:-5], "%Y%m%d%H"))
    
    files = sorted(files)
    sorted_files = []
    for i in files:
        sorted_files.append(path + "/drau_" + datetime.strftime(i, "%Y%m%d%H") + '.bufr')
    
    # get startday from parser
    start = parse_arguments().startday
    end = parse_arguments().endday
    
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
    #print(file)
    #open bufr file, convert to json (using "-j s") and load it with json.loads
    string = subprocess.check_output(r"bufr_dump -j f {}".format(file), shell=True)
    try:
        #string = subprocess.check_output(r"bufr_dump -j f {}".format(file), shell=True)
        string = subprocess.check_output(r"bufr_dump -j f {}".format(file), shell=True)
        json_file = json.loads(string)
        #print(string)
        #sys.exit()
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
                    print('this did not work')

        # sorting so that height of measurement equipment is a variable attribute instead of variable
        final_message = []        
        for msg in sorted_messages:
            height_measurements = ['007006', '007030', '007031', '007032', '007033'] # might have to add more codes here, check: https://confluence.ecmwf.int/display/ECC/WMO%3D30+element+table
            count_height = 0
            storing_height = []
            variables_with_height = []
            for i in msg:

                # if variable is a height of sensor etc, check if it is none. If not none, then add it as an attribute
                # for the consecutive variables until next height of sensor.
                if i['code'] in height_measurements and i['value'] != None:
                    count_height += 1
                    storing_height.append(i)
                if i['code'] in height_measurements and i['value'] == None:
                    count_height += 1
                    storing_height.append(None)

                if count_height == 0:
                    variables_with_height.append(i)
                if count_height != 0 and i['code'] not in height_measurements:
                    if storing_height[count_height-1] != None and i['key'] != 'timePeriod':
                        i['height'] = storing_height[count_height-1]
                    variables_with_height.append(i)

            final_message.append(variables_with_height)


        finale= []
        for msg in final_message:
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
    except:
        print('skipped this file: ' + file)
        return []



def return_list_of_stations(get_files):
    cfg = parse_cfg(parse_arguments().cfgfile)
    stationtype = parse_arguments().stationtype
    stations = []
    if stationtype == 'marine':
        for one_file in get_files:
            simple_file = bufr_2_json(one_file)
            for station in simple_file:
                if station[0]['key'] == 'marineObservingPlatformIdentifier':
                    station_num = str(station[0]['value'])
                    if station_num not in stations:
                        stations.append(station_num)
    if stationtype == 'buoy':
        for one_file in get_files:
            simple_file = bufr_2_json(one_file)
            for station in simple_file:
                if station[0]['key'] == 'buoyOrPlatformIdentifier':
                    station_num = str(station[0]['value'])
                    if station_num not in stations:
                        stations.append(station_num)
    return stations

def sorting_hat(get_files, stations = 1):
    cfg = parse_cfg(parse_arguments().cfgfile)
    
    #print(get_files)
    #sys.exit()
    if not parse_arguments().spec_station and stations == 1:
        stations = return_list_of_stations(get_files)
    elif parse_arguments().spec_station and stations == 1:
        stations = parse_arguments().spec_station
        
    stations_dict = {i : [] for i in stations}
    
    for one_file in get_files:
        simple_file = bufr_2_json(one_file)
        for station in simple_file:
            if str(station[0]['value']) in stations:
                stations_dict['{}'.format(str(station[0]['value']))].append(station)
    
    print('bufr successfully converted to json')
    print('sorting hat completed')
    
    return stations_dict

def buoyOrPlatformIdentifier(msg):
    tacos = []
    
    
    xars = []
    depth_ds = []
    other_ds = []
    df_units = []
    #print(msg)
    
    for i in msg:
        #print(msg)
        #sys.exit()
        #print(i)
        count1 = 0
        count2 = 0
        #acos = []
   
        depth = []
        other = []
        for_units = []
       
     
        for j in i:    
            for_units.append({j['key']: {'units':j['units'], 'code':j['code']}})
            if j['key'] == 'depthBelowWaterSurface':
                count1 += 1
                depth.append({'{}'.format(j['value']):[]})
            elif count1 != 0:
                depth[count1-1]['{}'.format(str(depth[count1-1].keys())[12:-3])].append(j)
            else:
                other.append(j)
        
                df = pd.DataFrame(filter_section(other))
        #print(df)
        # need to filter of some more 
        df = df[['key','value','units','code']].copy()

        
        df_vals = df[['key','value']].copy()

        df_vals = df_vals.transpose()
        df_vals = df_vals.reset_index()
        df_vals = df_vals.rename(columns=df_vals.iloc[0])
        df_vals = df_vals.drop(df.index[0])
        
        try:
            blob = blob = (str(int(df_vals['year'][1])).zfill(4) + '-' + str(int(df_vals['month'][1])).zfill(2) + '-' + str(int(df_vals['day'][1])).zfill(2) + ' ' + str(int(df_vals['hour'][1])).zfill(2) + ':' +  str(int(df_vals['minute'][1])).zfill(2) + ':' + str(int(df_vals['second'][1])).zfill(2))
            blob = datetime.strptime(blob, "%Y-%m-%d %H:%M:%S")
        except:
            blob = (str(int(df_vals['year'][1])).zfill(4) + '-' + str(int(df_vals['month'][1])).zfill(2) + '-' + str(int(df_vals['day'][1])).zfill(2) + ' ' + str(int(df_vals['hour'][1])).zfill(2) + ':' +  str(int(df_vals['minute'][1])).zfill(2))
            blob = datetime.strptime(blob, "%Y-%m-%d %H:%M")

        
        for k in depth:
            for l in k:
                taco = pd.DataFrame.from_dict(k[l])
                print(taco)
                sys.exit()
                taco = taco[['key','value']].copy().transpose().reset_index().drop(columns=['index'])
                header = taco.iloc[0]
                taco = taco[1:]
                taco.columns = header
                taco['depthBelowWaterSurface'] = k
                taco['index'] = count2
                taco = taco.set_index('index')
                #print(taco)
                #sys.exit()
                tacos.append(taco)
                count2 += 1
        #print(tacos)
        if len(tacos) > 1:
            full_taco = pd.concat(tacos[:-1])
        elif len(tacos) == 1:
            full_taco = tacos[0]
            for column in full_taco.columns:
                try:
                    full_taco[column] = pd.to_numeric(full_taco[column])
                except:
                    full_taco[column] = full_taco[column]
            full_taco = full_taco.reset_index()
            full_taco = full_taco[full_taco.depthBelowWaterSurface != 'None']
            #full_taco = full_taco.set_index('depthBelowWaterSurface')
            full_taco['time'] = [blob for i in range(len(full_taco['{}'.format(full_taco.columns[0])]))]
            full_taco = full_taco.set_index(['time','depthBelowWaterSurface'])
            #print(len(timet))
            #print(len(full_taco.columns[0]))
            #full_taco = full_taco.drop(columns=['index'])
            full_taco = full_taco.fillna(-9999)
            depth_ds.append(full_taco)
            #print(full_taco)
            #sys.exit()
        else:
            print('could not extract data')

        
            
        if 'second' in df_vals.columns:
            df_vals['time'] = blob
            df_vals = df_vals.drop(columns = ['key','year', 'month', 'day','hour', 'minute', 'second'])
        else:
            df_vals['time'] = blob
            df_vals = df_vals.drop(columns = ['key','year', 'month', 'day','hour', 'minute'])
            
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

    if len(depth_ds) >= 1:
        tik = pd.concat(depth_ds)
    else:
        message = ('no data')
        return message
        #print('no data')
        #sys.exit()
    #tik = tik[~tik.index.duplicated(keep='first')]
    #print(tik)
    #print(tik)
    tik = tik.to_xarray()
    #print(tik)
    #sys.exit()
    if len(other_ds) >= 1:
        tak = pd.concat(other_ds)
    else:
        message = ('no data')
        return message
        

    tak = tak.to_xarray()

    #tik = tik.assign_coords({'time': blob})
    #tik = tik.expand_dims('time')
        
    tik = tik.drop_duplicates(dim="time")
    tak = tak.drop_duplicates(dim="time")
    
    try:
        main_ds = xr.merge([tik,tak])
    except:
        print(tik)
        print(tak)
        sys.exit()
    if units_df.empty:
        units_df= pd.DataFrame({'key': ['something','to','make', 'it' ,'pass']})
    else:
        units_df = units(df_units)
    
    #main_ds = main_ds.sortby('time')
    # some variables only need the first value as they are not dependent on time
    vars_one_val = ['blockNumber', 'stationNumber','latitude',
                    'longitude', 'heightOfStation', 'wigosIdentifierSeries', 'wigosIssuerOfIdentifier',
                    'wigosIssueNumber','wigosLocalIdentifierCharacter']
    for i in main_ds.keys():
        if i in vars_one_val:
            main_ds[i] = main_ds[i].isel(time=0)
    
    to_get_keywords = []
    for variable in main_ds.keys():
        var = variable
        if variable[-2] == '.':
            var = variable[:-2]
        change_upper_case = re.sub('(?<!^)(?=\d{2})', '_',re.sub('(?<!^)(?=[A-Z])', '_', var)).lower()
        
        # checking for standardname
        standardname_check = cf_match(change_upper_case)
        if standardname_check != 'fail':
            main_ds[variable].attrs['standard_name'] = standardname_check
        
        # adding long name. if variable has a height attribute, add it in the long name. if variable has a time attribute, add it in the long name.
        long_name = re.sub('_',' ', change_upper_case)
        main_ds[variable].attrs['long_name'] = long_name
        
        # adding units, if units is a CODE TABLE or FLAG TABLE, it will overrule the previous set attributes to set new ones
        if variable in list(units_df['key']):
            main_ds[variable].attrs['units'] = units_df.loc[units_df['key'] == variable, 'units'].iloc[0]
        else:
            continue
        
        if main_ds[variable].attrs['units'] == 'deg':
            main_ds[variable].attrs['units'] = 'degrees'
        if main_ds[variable].attrs['units'] == 'Numeric':
            main_ds[variable].attrs['units'] = '1'
        if main_ds[variable].attrs['units'] == 'CODE TABLE':
            main_ds[variable].attrs['long_name'] = main_ds[variable].attrs['long_name'] + ' according to WMO code table ' + units_df.loc[units_df['key'] == variable, 'code'].iloc[0]  
            main_ds[variable].attrs['units'] = '1'
        elif main_ds[variable].attrs['units'] == 'FLAG TABLE':
            main_ds[variable].attrs['long_name'] = main_ds[variable].attrs['long_name'] + ' according to WMO flag table ' + units_df.loc[units_df['key'] == variable, 'code'].iloc[0]
            main_ds[variable].attrs['units'] = '1'

        # adding coverage_content_type
        thematicClassification = ['blockNumber', 'stationNumber', 'stationType']
        if variable in thematicClassification:
            main_ds[variable].attrs['coverage_content_type'] = 'thematicClassification'
        else:
            main_ds[variable].attrs['coverage_content_type'] = 'physicalMeasurement'
        #to_get_keywords.append(change_upper_case)

        # must rename if variable name starts with a digit
        timeunits = ['hour', 'second', 'minute', 'year', 'month', 'day']
        if change_upper_case[0].isdigit() == True and change_upper_case.split('_')[1].lower() in timeunits:
            fixing_varname = re.sub( r"([A-Z])", r" \1", variable).split()
            fixing_varname = fixing_varname[2:] + fixing_varname[:2] + ['s']
            fixing_varname = ''.join(fixing_varname)
            fixing_varname = fixing_varname[0].lower() + fixing_varname[1:]
            main_ds[fixing_varname] = main_ds[variable]
            main_ds = main_ds.drop([variable])
        
        # must also rename the ones that end with ".1"
        if variable[-2] == '.':
            new_name = variable.replace('.', '')
            main_ds[new_name] = main_ds[variable]
            main_ds = main_ds.drop([variable])
    
    #### GLOBAL ATTRIBUTES #####
    ################# REQUIRED GLOBAL ATTRIBUTES ###################
    # this probably might have to be modified
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
    
    #main_ds.attrs['keywords'] = keywords
    #main_ds.attrs['keywords_vocabulary'] = keywords_voc
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
    
    print(main_ds)
    return main_ds   

if __name__ == "__main__":
    parse = parse_arguments()
    
    cfg = parse_cfg(parse.cfgfile)
    destdir = cfg['output']['destdir']
    frompath = cfg['station_info']['path']
    
    if parse.startday != None:
        print('creating files from {}'.format(parse.startday))
        #if get_files_specified_dates(frompath) != None:
        #print(type(get_files_specified_dates(frompath)))
        sorted_files = sorting_hat(get_files_specified_dates(frompath))

        #print(sorted_files.keys)
        for key,val in sorted_files.items():
            if parse.stationtype == 'buoy':
                file = buoyOrPlatformIdentifier(sorted_files['{}'.format(key)])
        #    elif parse.stationtype == 'ship':
        #        file = shipOrMobileLandStationIdentifier(sorted_files['{}'.format(key)])
            #sys.exit()
            #saving = saving_grace(file, key, destdir)