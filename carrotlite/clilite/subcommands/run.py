import csv
import os, time
import datetime
import fnmatch
import sys
import click
import json
import carrotlite
import carrotlite.tools as tools

@click.group(help="Commands for mapping data to the OMOP CommonDataModel (CDM).")
def run():
    pass

@click.command()
@click.option("--rules-file",
              required=True,
              help="json file containing mapping rules")
@click.option("--output-dir",
              default=None,
              help="define the output directory for OMOP-format tsv files")
@click.option("--write-mode",
              default='w',
              type=click.Choice(['w','a']),
              help="force write-mode on output files")
@click.option("--person-file",
              required=True,
              help="File containing person_ids in the first column")
@click.option("--omop-ddl-file",
              required=True,
              help="File containing OHDSI ddl statements for OMOP tables")
@click.option("--omop-config-file",
              required=True,
              help="File containing additional / override json config for omop outputs")
@click.option("--saved-person-id-file",
              default=None,
              required=False,
              help="Full path to person id file used to save person_id state and share person_ids between data sets")
@click.option("--use-input-person-ids",
              required=False,
              default='N',
              help="Use person ids as input without generating new integers")
@click.option("--last-used-ids-file",
              default=None,
              required=False,
              help="Full path to last used ids file for OMOP tables - format: tablename\tlast_used_id, \nwhere last_used_id must be an integer")
@click.option("--log-file-threshold",
              required=False,
              default=0,
              help="Lower outcount limit for logfile output")
@click.argument("input-dir",
                required=False,
                nargs=-1)
def mapstream(rules_file, output_dir, write_mode, person_file, omop_ddl_file, omop_config_file, saved_person_id_file, use_input_person_ids, last_used_ids_file, log_file_threshold, input_dir):
    """
    Map to output using input streams
    """
    print(input_dir)
    if os.path.isdir(input_dir[0]) == False:
        print("Not a directory, input dir {0}".format(input_dir[0]))
        sys.exit(1)

    if os.path.isdir(output_dir) == False:
        print("Not a directory, output dir {0}".format(output_dir))
        sys.exit(1)

    if saved_person_id_file == None:
        saved_person_id_file = output_dir + "/" + "person_ids.tsv"
        if os.path.exists(saved_person_id_file):
            os.remove(saved_person_id_file)
   
    starttime = time.time()
    omopcdm = tools.omopcdm.OmopCDM(omop_ddl_file, omop_config_file)
    #print(omopcdm.dump_ddl())
    mappingrules = tools.mappingrules.MappingRules(rules_file, omopcdm)
    metrics = tools.metrics.Metrics(mappingrules.get_dataset_name(), log_file_threshold)
    nowtime = time.time()

    print("--------------------------------------------------------------------------------")
    print("Loaded mapping rules from: {0} after {1:.5f} secs".format(rules_file, (nowtime - starttime)))
    output_files = mappingrules.get_all_outfile_names()
    record_numbers = {}
    for output_file in output_files:
        record_numbers[output_file] = 1

    fhd = {}
    tgtcolmaps = {}

    try:
        # Add in a saved-person-file existence test and reload from it is necessary returning the last used integer
        if os.path.isfile(saved_person_id_file):
            person_lookup, last_used_integer = load_saved_person_ids(saved_person_id_file)
        else:
            person_lookup = {}
            last_used_integer = 1
        if last_used_ids_file != None:
            if os.path.isfile(last_used_ids_file):
                record_numbers = load_last_used_ids(last_used_ids_file, record_numbers)
 
        #fhp = open(person_file, mode="r", encoding="utf-8-sig")
        #csvrp = csv.reader(fhp)
        person_lookup, rejected_person_count = load_person_ids(person_file, person_lookup, mappingrules, use_input_person_ids, last_used_integer)
        fhpout = open(saved_person_id_file, mode="w")
        fhpout.write("SOURCE_SUBJECT\tTARGET_SUBJECT\n")
        for person_id, person_assigned_id in person_lookup.items():
            fhpout.write("{0}\t{1}\n".format(str(person_id), str(person_assigned_id)))
        fhpout.close()
        for tgtfile in output_files:
            fhd[tgtfile] = open(output_dir + "/" + tgtfile + ".tsv", mode=write_mode)
            if write_mode == 'w':
                outhdr = omopcdm.get_omop_column_list(tgtfile)
                fhd[tgtfile].write("\t".join(outhdr) + "\n")
            tgtcolmaps[tgtfile] = omopcdm.get_omop_column_map(tgtfile)

    except IOError as e:
        print("I/O - error({0}): {1} -> {2}".format(e.errno, e.strerror, str(e)))
        exit()

    print("person_id stats: total loaded {0}, reject count {1}".format(len(person_lookup), rejected_person_count))

    # TODO get this list of input files from the  parsed rules
    existing_input_files = fnmatch.filter(os.listdir(input_dir[0]), '*.csv')
    rules_input_files = mappingrules.get_all_infile_names()
    for infile in existing_input_files:
        if infile not in rules_input_files:
            msg = "ERROR: no mapping rules found for existing input file - {0}".format(infile)
            print(msg)
            metrics.add_log_data(msg)
    for infile in rules_input_files:
        if infile not in existing_input_files:
            msg = "ERROR: no data for mapped input file - {0}".format(infile)
            print(msg)
            metrics.add_log_data(msg)
    rejidcounts = {}
    rejdatecounts = {}
    #src_tgt_counts = {}
    print(rules_input_files)

    for srcfilename in rules_input_files:
        rejidcounts[srcfilename] = 0
        rejdatecounts[srcfilename] = 0

    for srcfilename in rules_input_files:
        outcounts = {}
        rejcounts = {}
        rcount = 0

        try:
            fh = open(input_dir[0] + "/" + srcfilename, mode="r", encoding="utf-8-sig")
            csvr = csv.reader(fh)
        except IOError as e:
            print("Unable to open: {0}".format(input_dir[0] + "/" + srcfilename))
            print("I/O error({0}): {1}".format(e.errno, e.strerror))
            continue

        tgtfiles, src_to_tgt = mappingrules.parse_rules_src_to_tgt(srcfilename)
        infile_datetime_source, infile_person_id_source = mappingrules.get_infile_date_person_id(srcfilename)
        for tgtfile in tgtfiles:
            outcounts[tgtfile] = 0
            rejcounts[tgtfile] = 0
        datacolsall = []
        hdrdata = next(csvr)
        dflist = mappingrules.get_infile_data_fields(srcfilename)
        for colname in hdrdata:
            datacolsall.append(colname)
        inputcolmap = omopcdm.get_column_map(hdrdata)
        pers_id_col = inputcolmap[infile_person_id_source]
        datetime_col = inputcolmap[infile_datetime_source]
        print("--------------------------------------------------------------------------------")
        print("Processing input: {0}".format(srcfilename))
#        print("Processing input: {0}, All input cols = {1}, Data cols = {2}".format(srcfilename, str(datacolsall), str(dflist)))

        for indata in csvr:
            #indata = inputline.strip().split(",")
            key = srcfilename + "~all~all~all~"
            metrics.increment_key_count(key, "input_count")
            rcount += 1
            strdate = indata[datetime_col].split(" ")[0]
            fulldate = parse_date(strdate)
            if fulldate != None:
                #fulldate = "{0}-{1:02}-{2:02}".format(dt.year, dt.month, dt.day)
                indata[datetime_col] = fulldate
            else:
                metrics.increment_key_count(key, "invalid_date_fields")
                continue

            for tgtfile in tgtfiles:
                tgtcolmap = tgtcolmaps[tgtfile]
                auto_num_col = omopcdm.get_omop_auto_number_field(tgtfile)
                pers_id_col = omopcdm.get_omop_person_id_field(tgtfile)

                datacols = datacolsall
                if tgtfile in dflist:
                    datacols = dflist[tgtfile]

                for datacol in datacols:
                    built_records, outrecords, metrics = get_target_records(tgtfile, tgtcolmap, src_to_tgt, datacol, indata, inputcolmap, srcfilename, omopcdm, metrics)
                    if built_records == True:
                        for outrecord in outrecords:
                            if auto_num_col != None:
                                outrecord[tgtcolmap[auto_num_col]] = str(record_numbers[tgtfile])
                                record_numbers[tgtfile] += 1
                            if (outrecord[tgtcolmap[pers_id_col]]) in person_lookup:
                                outrecord[tgtcolmap[pers_id_col]] = person_lookup[outrecord[tgtcolmap[pers_id_col]]]
                                outcounts[tgtfile] += 1
                                key = srcfilename + "~all~all~all~"
                                metrics.increment_key_count(key, "output_count")
                                key = "all~all~" + tgtfile + "~all~"
                                metrics.increment_key_count(key, "output_count")
                                key = srcfilename + "~all~" + tgtfile + "~all~"
                                metrics.increment_key_count(key, "output_count")
                                if tgtfile == "person":
                                    key = srcfilename + "~all~" + tgtfile + "~" + outrecord[1] +"~"
                                    metrics.increment_key_count(key, "output_count")
                                    key = srcfilename + "~" + datacol +"~" + tgtfile + "~" + outrecord[1] + "~" + outrecord[2]
                                    metrics.increment_key_count(key, "output_count")
                                else:
                                    key = srcfilename + "~" + datacol +"~" + tgtfile + "~" + outrecord[2] + "~"
                                    metrics.increment_key_count(key, "output_count")
                                    key = srcfilename + "~all~" + tgtfile + "~" + outrecord[2] + "~"
                                    metrics.increment_key_count(key, "output_count")
                                    key = "all~all~" + tgtfile + "~" + outrecord[2] + "~"
                                    metrics.increment_key_count(key, "output_count")
                                    key = "all~all~all~" + outrecord[2] + "~"
                                    metrics.increment_key_count(key, "output_count")
                                fhd[tgtfile].write("\t".join(outrecord) + "\n")
                            else:
                                key = srcfilename + "~all~" + tgtfile + "~all~"
                                metrics.increment_key_count(key, "invalid_person_ids")
                                rejidcounts[srcfilename] += 1

        fh.close()

        nowtime= time.time()
        print("INPUT file data : {0}: input count {1}, time since start {2:.5} secs".format(srcfilename, str(rcount), (nowtime - starttime)))
        for outtablename, count in outcounts.items():
            print("TARGET: {0}: output count {1}".format(outtablename, str(count)))

    print("--------------------------------------------------------------------------------")
    data_summary = metrics.get_mapstream_summary()
    log_report = metrics.get_log_data()
    try:
        dsfh = open(output_dir + "/summary_mapstream.tsv", mode="w")
        dsfh.write(data_summary)
        dsfh.close()
        logfh = open(output_dir + "/error_report.txt", mode="w")
        logfh.write(log_report)
        logfh.close()
    except IOError as e:
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        print("Unable to write file")

    nowtime = time.time()
    print("Elapsed time = {0:.5f} secs".format(nowtime - starttime))
    #profiler.disable()
    #stats = pstats.Stats(profiler).sort_stats('ncalls')
    #stats.print_stats()

def get_target_records(tgtfilename, tgtcolmap, rulesmap, srcfield, srcdata, srccolmap, srcfilename, omopcdm, metrics):
    build_records = False
    tgtrecords = []
    date_col_data = omopcdm.get_omop_datetime_linked_fields(tgtfilename)
    date_component_data = omopcdm.get_omop_date_field_components(tgtfilename)
    notnull_numeric_fields = omopcdm.get_omop_notnull_numeric_fields(tgtfilename)

    srckey = srcfilename + "~" + srcfield + "~" + tgtfilename
    summarykey = srcfilename + "~" + srcfield + "~" + tgtfilename + "~all~"
    if valid_value(str(srcdata[srccolmap[srcfield]])):
        srcfullkey = srcfilename + "~" + srcfield + "~" + str(srcdata[srccolmap[srcfield]]) + "~" + tgtfilename
        dictkeys = []
        if srcfullkey in rulesmap:
            build_records = True
            dictkeys.append(srcfullkey)
        if srckey in rulesmap:
            build_records = True
            dictkeys.append(srckey)
        if build_records == True:
            for dictkey in dictkeys:
                for out_data_elem in rulesmap[dictkey]:
                    valid_data_elem = True
                    tgtarray = ['']*len(tgtcolmap)
                    for req_integer in notnull_numeric_fields:
                        tgtarray[tgtcolmap[req_integer]] = "0"
                    for infield, outfield_list in out_data_elem.items():
                        for output_col_data in outfield_list:
                            if "~" in output_col_data:
                                outcol, term = output_col_data.split("~")
                                tgtarray[tgtcolmap[outcol]] = term
                            else:
                                tgtarray[tgtcolmap[output_col_data]] = srcdata[srccolmap[infield]]
                            if output_col_data in date_component_data:
                                strdate = srcdata[srccolmap[infield]].split(" ")[0]
                                dt = get_datetime_value(strdate)
                                if dt != None:
                                    year_field = date_component_data[output_col_data]["year"]
                                    month_field = date_component_data[output_col_data]["month"]
                                    day_field = date_component_data[output_col_data]["day"]
                                    tgtarray[tgtcolmap[year_field]] = str(dt.year)
                                    tgtarray[tgtcolmap[month_field]] = str(dt.month)
                                    tgtarray[tgtcolmap[day_field]] = str(dt.day)
                                    fulldate = "{0}-{1:02}-{2:02}".format(dt.year, dt.month, dt.day)
                                    tgtarray[tgtcolmap[output_col_data]] = fulldate
                                else:
                                    metrics.increment_key_count(summarykey, "invalid_date_fields")
                                    valid_data_elem = False
                            elif output_col_data in date_col_data:
                                fulldate = srcdata[srccolmap[infield]]
                                tgtarray[tgtcolmap[output_col_data]] = fulldate
                                tgtarray[tgtcolmap[date_col_data[output_col_data]]] = fulldate
                    if valid_data_elem == True:
                        tgtrecords.append(tgtarray)
    else:
        metrics.increment_key_count(summarykey, "invalid_source_fields")


    return build_records, tgtrecords, metrics

def valid_value(item):
    """
    Check if an item is non blank (null)
    """
    if item.strip() == "":
        return(False)
    return(True)

def valid_date_value(item):
    """
    Check if a date item is non null and parses as ISO (YYYY-MM-DD), reverse-ISO
    or dd/mm/yyyy or mm/dd/yyyy
    """
    if item.strip() == "":
        return(False)
    if not valid_iso_date(item) and not valid_reverse_iso_date(item) and not valid_uk_date(item):
        #print("Bad date : {0}".format(item))
        return(False)
    return(True)

def get_datetime_value(item):
    """
    Check if a date item is non null and parses as ISO (YYYY-MM-DD), reverse-ISO
    or dd/mm/yyyy or mm/dd/yyyy
    """
    dt = None
    # Does the date parse as an ISO date?
    try:
        dt = datetime.datetime.strptime(item, "%Y-%m-%d")
    except ValueError:
        pass
    if dt != None:
      return(dt)

    # Does the date parse as a reverse ISO date?
    try:
        dt = datetime.datetime.strptime(item, "%d-%m-%Y")
    except ValueError:
        pass

    if dt != None:
      return(dt)

    # Does the date parse as a UK old-style date?
    try:
        dt = datetime.datetime.strptime(item, "%d/%m/%Y")
    except ValueError:
        pass

    if dt != None:
      return(dt)

    return None

def parse_date(item):
    """
    Crude hand-coded check on date format
    """
    datedata = item.split("-")
    if len(datedata) != 3:
        datedata = item.split("/")
    if len(datedata) != 3:
        return None
    if len(datedata[2]) == 4:
        return("{0}-{1}-{2}".format(datedata[2], datedata[1], datedata[0]))
    return("{0}-{1}-{2}".format(datedata[0], datedata[1], datedata[2]))


def valid_iso_date(item):
    """
    Check if a date item is non null and parses as ISO (YYYY-MM-DD)
    """
    try:
        datetime.datetime.strptime(item, "%Y-%m-%d")
    except ValueError:
        return(False)

    return(True)

def valid_reverse_iso_date(item):
    """
    Check if a date item is non null and parses as reverse ISO (DD-MM-YYYY)
    """
    try:
        datetime.datetime.strptime(item, "%d-%m-%Y")
    except ValueError:
        return(False)

    return(True)

def valid_uk_date(item):
    """
    Check if a date item is non null and parses as UK format (DD/MM/YYYY)
    """
    try:
        datetime.datetime.strptime(item, "%d/%m/%Y")
    except ValueError:
        return(False)

    return(True)

def load_last_used_ids(last_used_ids_file, last_used_ids):
    fh = open(last_used_ids_file, mode="r", encoding="utf-8-sig")
    csvr = csv.reader(fh, delimiter="\t")

    for last_ids_data in csvr:
        last_used_ids[last_ids_data[0]] = int(last_ids_data[1]) + 1

    fh.close()
    return last_used_ids

def load_saved_person_ids(person_file):
    fh = open(person_file, mode="r", encoding="utf-8-sig")
    csvr = csv.reader(fh, delimiter="\t")
    last_int = 1
    person_ids = {}

    next(csvr)
    for persondata in csvr:
        person_ids[persondata[0]] = persondata[1]
        last_int += 1

    fh.close()
    return person_ids, last_int

def load_person_ids(person_file, person_ids, mappingrules, use_input_person_ids, person_number=1, delim=","):
    fh = open(person_file, mode="r", encoding="utf-8-sig")
    csvr = csv.reader(fh, delimiter=delim)
    person_columns = {}
    person_col_in_hdr_number = 0
    reject_count = 0

    personhdr = next(csvr)
    print(personhdr)

    # Make a dictionary of column names vs their positions
    for col in personhdr:
        person_columns[col] = person_col_in_hdr_number
        person_col_in_hdr_number += 1

    birth_datetime_source, person_id_source = mappingrules.get_person_source_field_info("person")
    print("Load Person Data {0}, {1}".format(birth_datetime_source, person_id_source))
    person_col = person_columns[person_id_source]

    for persondata in csvr:
        if not valid_value(persondata[person_columns[person_id_source]]):
            reject_count += 1
            continue
        if not valid_date_value(persondata[person_columns[birth_datetime_source]]):
            reject_count += 1
            continue
        if persondata[person_col] not in person_ids:
            if use_input_person_ids == "N":
                person_ids[persondata[person_col]] = str(person_number)
                person_number += 1
            else:
                person_ids[persondata[person_col]] = str(persondata[person_col])
    fh.close()

    return person_ids, reject_count

@click.group(help="Commands for using python configurations to run the ETL transformation.")
def py():
    pass

run.add_command(mapstream,"mapstream")
