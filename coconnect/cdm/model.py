import os
import pandas as pd
import numpy as np
import json
import copy
import collections

from .operations import OperationTools
from coconnect.tools.logger import Logger
from .objects import Person, ConditionOccurrence

_classes = {
    'person' : Person,
    'condition_occurrence' : ConditionOccurrence
}

class NoInputFiles(Exception):
    pass

class CommonDataModel:

    def __init__(self,inputs=None,_start_on_init=True):
        self.logger = Logger(self.__class__.__name__)
        self.logger.info("CommonDataModel created")

        self.inputs = inputs
        
        if _start_on_init:
            self.tools = OperationTools()
            self.__dict__.update(self.__class__.__dict__)

            if self.inputs == None:
                raise NoInputFiles('You need to set or specify the input files.') 

            self.finalise()
            
    def apply_term_map(self,f_term_mapping):
        self.df_term_mapping = pd.read_csv(f_term_mapping)

        self.df_term_mapping = self.df_term_mapping.set_index('rule_id').sort_index()
        self.df_structural_mapping= self.df_structural_mapping\
            [self.df_structural_mapping['term_mapping'].str.contains('y')].reset_index().set_index('rule_id').sort_index()
        
        maps = self.df_term_mapping.join(self.df_structural_mapping)\
                                   .set_index(['destination_table','destination_field'])\
                                   [['source_term','destination_term','term_mapping']].sort_index()

        
        for p in self.get_objs(Person):
            person_map = maps.loc['person']
            for destination_field in person_map.index.unique():
                term_mapper = maps.loc[p.name,destination_field]\
                             .reset_index(drop=True)\
                             .set_index('source_term')['destination_term']\
                             .to_dict()
                print ('mapping',destination_field,'with',term_mapper)
                print (maps.loc[p.name,destination_field])
                mapped_field = getattr(p,destination_field).map(term_mapper)
                setattr(p,destination_field,mapped_field)
                
            exit(0)
        

    def get_cdm_class(self,class_type):
        if class_type in _classes:
            return _classes[class_type]()
    
    def get_objs(self,class_type):
        self.logger.debug(f"looking for {class_type}")
        return  [
            getattr(self,x)
            for x in dir(self)
            if isinstance(getattr(self,x),class_type)
        ]
    
    def run_cdm(self,class_type):
        objects = self.get_objs(class_type)
        nobjects = len(objects)
        extra = ""
        if nobjects>1:
            extra="s"
        self.logger.info(f"for {class_type.name}: found {nobjects} object{extra}")
        
        if len(objects) == 0:
            return
        
        #execute them all
        dfs = []
        for obj in objects:
            obj.execute(self)
            df = obj.get_df()
            if len(df) == 0:
                continue
            dfs.append(df)

        #merge together
        df_destination = pd.concat(dfs,ignore_index=True)
        df_destination = class_type.finalise(class_type,df_destination)
        
        return df_destination

        
    def finalise(self,f_out='output_data/'):
        self.df_map = {}
        self.df_map[Person.name] = self.run_cdm(Person)
        self.df_map[ConditionOccurrence.name] = self.run_cdm(ConditionOccurrence)

        self.save_to_file(self.df_map,f_out)
        
    def save_to_file(self,df_map,f_out):
        for name,df in df_map.items():
            if df is None:
                continue
            fname = f'{f_out}/{name}.csv'
            self.logger.info(f'saving {name} to {fname}')
            df.set_index(df.columns[0],inplace=True)
            df.to_csv(fname,index=True)
            self.logger.info(df.dropna(axis=1,how='all'))
        

