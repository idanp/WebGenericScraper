#!/usr/bin/env python3

import argparse
from bs4 import BeautifulSoup
import requests
import logging
from datetime import datetime
import json
import pandas as pd
import os
import yaml
import re
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
import time
from colorama import Fore
from colorama import Style

from WLO.src.WorkerAbs import *
from WLO.src.Utils.Utils import *

#from setup import VERSION
VERSION = '0.0.1'
POTENTIAL_DYNAMIC_JS_CONTENT = 'Please enable Javascript to use this application'
SERVICE="Scraper - "



def prep_text(txt,with_line_breaker=True):
    if with_line_breaker:
        return f'\n{Fore.GREEN}{txt}{Style.RESET_ALL}\n'
    else:
        return f'{Fore.GREEN}{txt}{Style.RESET_ALL}'

def prep_title(txt):
    return f'\n{Fore.BLUE}{txt}{Style.RESET_ALL}\n'


DRIVER_PREFIX = "Worker-Driver-WebScraping: "



class WebSiteScarperWorker(WorkerAbstract):

    def __init__(self):
        logging.info(f"{DRIVER_PREFIX}Creating scraper worker")
        self.file_name = ''
        self.execution_vars = {}

    def work(self, msg):

            logging.info(f"{DRIVER_PREFIX}Start!!")

            working_params = msg['params']
            self.execution_vars['title'] = working_params['title'] if 'title' in working_params else None
            payload = msg['payload']

            URL = payload['url_to_scrap']
            self.file_name = URL.split('/')[len(URL.split('/'))-1]
            scrap_flow = None


            if 'scrap_flow' in payload:
                scrap_path = payload['scrap_flow']
                with open(f'{scrap_path}') as file:
                    scrap_flow = yaml.load(file, Loader=yaml.FullLoader)

            if 'inline_scrap_flow' in payload:
                scrap_flow = payload['inline_scrap_flow']



            # pre process steps - mostly for prettify the html or get dynamic contents
            if 'preProcess' in scrap_flow:
                action = scrap_flow['preProcess'][0]
                page = self.execute_action(URL, action)
                soup = BeautifulSoup(page, 'html.parser')

            else:
                page = requests.get(URL)
                soup = BeautifulSoup(page.content, 'html.parser')

                if POTENTIAL_DYNAMIC_JS_CONTENT in soup.text:
                    soup = BeautifulSoup(self.get_html_from_js(URL), 'html.parser')

            # Scrap the web page according to the yaml flow
            for link in scrap_flow['flow']:
                self.execute_action(soup, link)
            return

    def expend_dynamic_HTML(self, URL, action_type, element, contain_element):
        from selenium import webdriver
        import time

        driver = webdriver.Chrome(ChromeDriverManager().install())
        driver.get(URL)
        time.sleep(5)


        # get the container element
        if contain_element:
            contain_element_class = contain_element['class'] if 'class' in contain_element else None
            contain_element_id = contain_element['id'] if 'id' in contain_element else None
            contain_element_html_type = contain_element['HTMLtype'] if 'HTMLtype' in contain_element else None
            contain_element_value = contain_element['elementVal'] if 'elementVal' in contain_element else None
            elements = self.get_elemnt_by(contain_element_class, contain_element_id, contain_element_html_type, contain_element_value, driver)

            for soup_element in elements:
                self.html_dynamic_expend_click(element=element, soup=soup_element)
        else:
            self.html_dynamic_expend_click(element=element, soup=driver)

        htmlSource = driver.page_source
        return htmlSource

    def html_dynamic_expend_click(self,element, soup ):
        element_class = element['class'] if 'class' in element else None
        element_id = element['id'] if 'id' in element else None
        element_type = element['elementType'] if 'elementType' in element else None
        element_value = element['elementVal'] if 'elementVal' in element else None
        element_html_type = element['HTMLtype'] if 'HTMLtype' in element else None

        elements = self.get_elemnt_by(element_class, element_id, element_html_type, element_value, soup)
        while(len(elements)>0):
            child_elements = []
            if element_type == 'list':
                for element in elements:
                    element.click()
                    child_elements.extend(self.get_elemnt_by(element_class, element_id, element_html_type, element_value, element))
            elements = child_elements.copy()


    def get_elemnt_by(self, element_class, element_id, element_html_type, element_value, soup):

        elements = []
        if element_class:
            elements = soup.find_elements_by_class_name(element_class)
        if element_id:
            elements = soup.find_elements_by_id(element_id)

        if element_html_type:
            filtered_elements = []
            for element in elements:
                if element.tag_name == element_html_type:
                    filtered_elements.append(element)
            elements = filtered_elements.copy()

        if element_value:
            filtered_elements = []
            for element in elements:
                if element.text == element_value:
                    filtered_elements.append(element)
            elements = filtered_elements.copy()

        return elements

    def get_html_from_js(self, URL):


        driver = webdriver.Chrome()
        driver.get(URL)
        time.sleep(5)
        htmlSource = driver.page_source
        driver.close()
        return htmlSource

    def execute_action(self, target_value ,execution_plan):
        result = None

        action_name = execution_plan['actionName']
        action_params = execution_plan['actionParams'] if 'actionParams' in execution_plan else []
        sub_actions = execution_plan['subActions'] if 'subActions' in execution_plan else []
        action_type = execution_plan['actionType'] if 'actionType' in execution_plan else 'Atomic'

        single_action_result = self.run_single_action(target_value, action_name, action_params)

        if len(sub_actions) > 0:
            for action in sub_actions:
                if 'actionType' in action:
                    if action['actionType'] == 'loop':
                        for elem in single_action_result:
                            result = self.execute_action(elem, action)
                    elif action['actionType'] == 'rec':
                        result = self.execute_action(single_action_result, action)
                    elif action['actionType'] == 'tree_dfs':
                        for branch in self.get_dfs_branches(tree=single_action_result):
                            result = self.execute_action(branch, action)

                # loop over the current element and execute set of action per element in the loop
                elif 'type' in action:
                    if action['type'] == 'loop':
                        actions = action['actions']
                        for elem in single_action_result:
                            for sub_action in actions:
                                result = self.execute_action(elem, sub_action)

                else:
                    result = self.run_single_action(single_action_result, action['actionName'], action['actionParams'])
        else:
            result = single_action_result

        return result



    def run_single_action(self, target_value, action_name, action_params):

        if action_name == 'expendDynamicHTML':
            logging.info(f"{SERVICE}Start expand dynamic HTML")
            action_type = action_params['type']
            element = action_params['Element']
            contain_element = action_params['containElement'] if 'containElement' in action_params else None
            return self.expend_dynamic_HTML(URL=target_value, action_type=action_type, element=element, contain_element=contain_element)

        # in this case target_value should be BeautifulSoup
        # todo - add asChild condition to path - to get the path that has specific child
        if action_name == 'path':
            logging.info(f"{SERVICE}path action")
            id_ = action_params['id'] if 'id' in action_params else None
            class_ = action_params['class'] if 'class' in action_params else None
            exclude = action_params['exclude'] if 'exclude' in action_params else None
            attr = action_params['attr'] if 'attr' in action_params else None
            elem_soup = self.HTMLpath(target_value, action_params['type'], action_params['HTMLtype'], id_, class_,attr, exclude)
            return elem_soup
        
        if action_name == 'table2csv':
            logging.info(f"{SERVICE}table2csv action")
            id_ = action_params['id'] if 'id' in action_params else None
            class_ = action_params['class'] if 'class' in action_params else None
            pre_defined_columns = action_params['preDefinedColumns'] if 'preDefinedColumns' in action_params else {}
            num_of_column_to_enforce = action_params['numOfColumnToEnforce'] if 'numOfColumnToEnforce' in action_params else -1
            data_frame = self.table2csv(target_value, id_, class_, pre_defined_columns,num_of_column_to_enforce)
            return data_frame
        
        if action_name == 'buildConnectionTree':
            logging.info(f"{SERVICE}buildConnectionTree action")
            starting_point = action_params['StartintPoint'] if 'StartintPoint' in action_params else None
            ending_point = action_params['EndingPoint'] if 'EndingPoint' in action_params else None
            tree_relations = action_params['treeRelations']
            save_to_var = action_params['saveToVar'] if 'saveToVar' in action_params else None
            tree = self.build_connection_tree(target_value=target_value,
                                              starting_point=starting_point,
                                              ending_point=ending_point,
                                              tree_relations=tree_relations,
                                              save_to_var=save_to_var)
            return tree[1]



        # tree to csv,
        if action_name == 'treeBranch2csv':
            logging.info(f"{SERVICE}treeBranch2csv action")
            html_table_idx =  action_params['idxOfHtmlTable'] if 'idxOfHtmlTable' in action_params else  None
            pre_defined_columns = action_params['preDefinedColumns'] if 'preDefinedColumns' in action_params else None
            data_frame = self.tree_branch_to_csv(branch=target_value, html_table_idx = html_table_idx, pre_defined_columns=pre_defined_columns)
            return data_frame



        # in this case target_value should be BeautifulSoup
        if action_name == 'get':
            logging.info(f"{SERVICE}get action")
            val = action_params['value']
            fix_text_flag = action_params['fixText'] if 'fixText' in action_params else None

            if val == 'text':
                if fix_text_flag:
                    return self.fix_text(target_value.text)
                else:
                    return target_value.text
            else:
                if fix_text_flag:
                    return self.fix_text(target_value.get(val))
                else:
                    return target_value.get(val)

        # in this case target_value should be string
        if action_name == 'substring':
            logging.info(f"{SERVICE}substring action")
            start = action_params['start'] if 'start' in action_params else 0
            end = action_params['end'] if 'end' in action_params else len(target_value)
            return target_value[start:end]

        if action_name == 'concat':
            logging.info(f"{SERVICE}concat action")
            prefix = action_params['prefix'] if 'prefix' in action_params else ''
            suffix = action_params['suffix'] if 'suffix' in action_params else ''
            return prefix+target_value+suffix

        if action_name == 'createVar':
            logging.info(f"{SERVICE}createVar action")
            var = self.create_execution_var(action_params)
            self.execution_vars[var[0]] = var[1]
            return var

        if action_name == 'saveToFile':
            logging.info(f"{SERVICE}saveToFile action")
            dateTimeObj = datetime.now()
            file_name_prefix = action_params['name_prefix'] if 'name_prefix' in action_params else None

            if action_params['longName']:
                file_name = action_params['to']+"-"+str(dateTimeObj)
            else:
                file_name = action_params['to']

            if file_name_prefix:
                if '$' in file_name_prefix:
                    file_name_prefix = self.execution_vars[file_name_prefix[1:]]
                file_name = file_name_prefix+"_"+file_name


            if 'dir' in action_params:
                dir_name = action_params['dir']
                if not os.path.exists(dir_name):
                    os.mkdir(dir_name)
                file_name = os.path.join(dir_name, file_name)


            if action_params['fileType'] == 'json':

                file_name = file_name+".json"
                with open(file_name, 'a') as file:
                    json.dump(target_value, file, indent=4)

            # in this case assuming that target_value is data_frame
            if action_params['fileType'] == 'csv':
                file_name = file_name + ".csv"
                target_value.to_csv(file_name, index=False, sep=',', encoding='utf-8')

        if action_name == 'addToVar':
            logging.info(f"{SERVICE}addToVar action")
            var_name = action_params['varName']
            var_type = action_params['varType']
            var_key = action_params['varKey'] if 'varKey' in action_params else None


            if var_key and '$' in var_key:
                if var_key == '$.':
                    var_key = target_value
                else:
                    var_key = self.execution_vars[var_key[1:]]

            var_value = action_params['varValue'] if 'varValue' in action_params else target_value
            if '$' in var_value:
                var_value = self.execution_vars[var_value[1:]]
            if var_type == 'list':
                self.execution_vars[var_name].append(var_value)
            if var_type == 'dict':
                self.execution_vars[var_name][var_key] = var_value
            if var_type == 'str':
                self.execution_vars[var_name] = var_value
            return target_value

        if action_name == 'removeVar':
            logging.info(f"{SERVICE}removeVar action")
            var_name = action_params['varName']
            var_type = action_params['varType']
            var_key = action_params['varKey'] if 'varKey' in action_params else None
            var_value = action_params['varValue'] if 'varValue' in action_params else target_value
            if '$' in var_value:
                var_value = self.execution_vars[var_value[1:]]

            if var_key and '$' in var_key:
                var_key = self.execution_vars[var_key[1:]]
            if var_type == 'list':
                self.execution_vars[var_name].remove(var_value)
            if var_type == 'dict':
                self.execution_vars[var_name].pop(var_key)

        if action_name == 'getVar':
            logging.info(f"{SERVICE}getVar action")
            var_name = action_params['varName']
            return self.execution_vars[var_name]

        if action_name == 'cleanVar':
            logging.info(f"{SERVICE}cleanVar action")
            var_name = action_params['varName']
            if type(self.execution_vars[var_name]) == list:
                self.execution_vars[var_name] = []
            elif type(self.execution_vars[var_name]) == dict:
                self.execution_vars[var_name] = {}
            else:
                self.execution_vars[var_name] = ""

    def HTMLpath(self, soup , type, HTMLtype, id_, class_,attr,  exclude):
        logging.debug(f"{DRIVER_PREFIX}Going to scrap - {HTMLtype}, id - {id_}, class - {class_}")
        sub_soup = None
        if type == 'single':
            if id_:
                sub_soup = soup.find(HTMLtype, id=id_)
            elif class_:
                sub_soup = soup.find(HTMLtype, class_=class_)
            elif attr:
                sub_soup = soup.find(HTMLtype, attrs=attr)
            else:
                sub_soup = soup.find(HTMLtype)
        else:
            if id_:
                sub_soup = soup.findAll(HTMLtype, id=id_)
            elif class_:
                sub_soup = soup.findAll(HTMLtype, class_=class_)
            elif attr:
                sub_soup = soup.findAll(HTMLtype, attrs=attr)
            else:
                sub_soup = soup.findAll(HTMLtype)

        logging.debug(f"{DRIVER_PREFIX}Going to exclude tags")
        # exclude by identifier
        if exclude:
            for item in exclude:
                html_type = item['type']
                value_to_exclude = item['value']
                for elem in sub_soup:
                    if elem.has_attr(html_type) or elem.name == html_type:
                        if value_to_exclude == elem.get('id') or value_to_exclude == elem.text or value_to_exclude in elem.get('class'):
                            sub_soup.remove(elem)

        return sub_soup

    def create_execution_var(self, action_params):
        name = action_params['name']
        value = action_params['value'] if 'value' in action_params else ''
        if action_params['type'] == 'list':
            return name, []
        if action_params['type'] == 'dict':
            return name, {}
        return name, value

    def table2csv(self, soup, id_=None, class_=None, pre_defined_columns={}, num_of_column_to_enforce=-1):
        data = []

        # getting the header and data from the HTML file

        if id_:
            header = soup.findAll("table", id=id_)[0].find("tr")
            HTML_data = soup.find_all("table", id=id_)[0].find_all("tr")[1:]
        elif class_:
            header = soup.findAll("table", class_=class_)[0].find("tr")
            HTML_data = soup.find_all("table", class_=class_)[0].find_all("tr")[1:]
        else:
            header = soup.findAll("table")[0].find("tr")
            HTML_data = soup.find_all("table")[0].find_all("tr")[1:]

        list_header = []
        for pre_def_col_header, pre_def_val in pre_defined_columns.items():
            list_header.append(pre_def_col_header)

        for items in header:
            try:
                list_header.append(self.fix_text(items.get_text()).replace(' ','_'))
            except:
                continue

        pre_defined_sub_data = []
        for pre_def_header, pre_def_val in pre_defined_columns.items():
            if '$' in pre_def_val:
                value = pre_def_val[1:]

                # treating a list value
                if '.' in value:
                    if 'pop' in value:
                        value = value[0:value.index('.')]
                        pre_defined_val = self.execution_vars[value].pop(0)
                    else:

                        value_idx = value[value.index('.'):]
                        value = value[0:value.index('.')]
                        pre_defined_val = self.execution_vars[value][value_idx]
                # treating direct variable value
                else:
                    pre_defined_val = self.execution_vars[value]
            # use hard text as value
            else:
                pre_defined_val = pre_def_val
            pre_defined_sub_data.append(pre_defined_val)

        for element in HTML_data:
            # can get rid of unneeded row splits
            if num_of_column_to_enforce != -1:
                if len(element.findAll('td')) != num_of_column_to_enforce:
                    continue
            sub_data = []
            for pre_data in pre_defined_sub_data:
                sub_data.append(pre_data)


            for sub_element in element:
                try:
                    sub_data.append(self.fix_text(sub_element.get_text()))
                except:
                    continue
            data.append(sub_data)

            # Storing the data into Pandas
        # DataFrame
        data_frame = pd.DataFrame(data=data, columns=list_header)
        return data_frame

    def fix_text(self, text):
        final_val = text.lstrip().rstrip().replace('"', '')
        return ' '.join(final_val.split())

    def build_connection_tree(self, target_value, starting_point, ending_point, tree_relations, save_to_var):
        '''
        This method iterate over all the childrens tags of target_value and from stating_point we build an
        hierarchy tree based on tree_relations (in case we have flat html that parent some parent-child relations
        We can use this method for translate the flat order into a relations.
        For example:
                        <h2>...</h2>
                        <h3>...</h3>
                        <div> ...</div>
        and we want to represent it as h2.h3.div

        output:
            h2:{
                h3:{
                    div{}
                    }
            }


        :param ending_point: The  position (element) in the target value where se stop thew itteration
        :param starting_point: Where in the target_vlaue tag to start iterate
        :param target_value: The current HTML section
        :param tree_relations: What should be the relation
        :param save_to_var: WHich var to save the results (optional)
        :return: dic
        '''

        tree = {}
        starting_point_idx = 0
        ending_point_idx = len(target_value.find_all_next())

        if starting_point:
            starting_point_elem_type = ""
            starting_identifiers = {}
            for elem_type, identifiers in starting_point.items():
                starting_point_elem_type = elem_type
                starting_identifiers = identifiers

            starting_point_idx = self._find_position(target_value, starting_point_elem_type, starting_identifiers)

        if ending_point:
            ending_point_elem_type = ""
            ending_identifiers = {}
            for elem_type, identifiers in ending_point.items():
                ending_point_elem_type = elem_type
                ending_identifiers = identifiers
            ending_point_idx = self._find_position(target_value, ending_point_elem_type, ending_identifiers)

        #build the hierarchy level
        hierarchy_level = tree_relations.split('.')
        hierarchy_level_dic ={}
        for level, elem_type in enumerate(hierarchy_level):
            hierarchy_level_dic[elem_type] = level
        lower_hierarchy = 0
        for key, val in hierarchy_level_dic.items():
            if val > lower_hierarchy:
                lower_hierarchy = val


        # start build the tree
        elements = target_value.find_all_next()

        tree = self._build_tree_recursive(current_level=0,
                                          elements=elements,
                                          index=starting_point_idx,
                                          end_idx=ending_point_idx,
                                          hierarchy_level_dic=hierarchy_level_dic,
                                          lower_hierarchy=lower_hierarchy)
        return tree


    def _build_tree_recursive(self, current_level, elements, index, end_idx, hierarchy_level_dic, lower_hierarchy):
        '''
        Recursive method for building tree from flat array based on elements types and hierarchy level definitions
        :param current_level: The current level in the tree
        :param elements: the array of elements
        :param index: the current index to retrieve from the array
        :param end_idx: the index that mark the end of the recursion
        :param hierarchy_level_dic: fix definition of how the hierarchy in the threshold looks like (based on elements types)
                for example - {h2:0,h3:1,div:2} - in that case h2 is the highest level , h3 in the middle oif the tree and div is the leaf
        :param lower_hierarchy: the leaf level
        :return:
        '''

        res = {}
        leaf=[]
        while index != end_idx:
            elem = elements[index]
            elem_type = elem.name
            index = index+1
            while elem_type not in hierarchy_level_dic:
                elem = elements[index]
                elem_type = elem.name
                index = index + 1

            elem_level = hierarchy_level_dic[elem_type]
            if elem_level == lower_hierarchy:
                current_level = elem_level
                leaf.append(elem)
                index = index+1
            elif elem_level >= current_level:
                current_level = elem_level
                index, res[elem] = self._build_tree_recursive(elem_level, elements, index, end_idx, hierarchy_level_dic, lower_hierarchy)
            else:
                if current_level == lower_hierarchy:
                    res['leaf'] = leaf
                return index-1,res
        return index, res


    def _find_position(self, target_value, position_elem_type, identifiers):
        for idx, elem in enumerate(target_value.find_all_next()):
            if elem.name == position_elem_type:
                all_match = True
                for identifier, identifier_val in identifiers.items():
                    if not elem.has_attr(identifier):
                        all_match = False
                        break
                    if not elem.get(identifier) == identifier_val:
                        all_match = False
                        break

                # found the starting point
                if all_match:
                    return idx

    def tree_branch_to_csv(self, branch, html_table_idx,  pre_defined_columns):
        '''
        take branch of a tree (represented as array)
        convert it to csv (if the leaf is a html table the csv will be the table and the other branch layers as pre defined columns (static values in the csv)

        :param branch: array of html elemnts
        :param html_table_idx: optional but if exist remark that the conversion strategic is based on table2csv method
                the value fo this filed is the index of the html table at the branch params
        :param pre_defined_columns: optional - if exist contain key value -
        {column name: <idx of the html element in the branch param> or static value  to use as pre defined column in the csv)
        :return: pandas data frame represnt csv table
        '''
        pre_def_columns_completed = dict()
        for key, val in pre_defined_columns.items():
            regexp_res = re.search(r"\[([A-Za-z0-9_]+)\]", val)
            pre_def_columns_completed[key] = branch[int(regexp_res.group(1))].text

        if html_table_idx:
            return self.table2csv(soup=branch[html_table_idx], pre_defined_columns=pre_def_columns_completed)
        else:
            data=[]
            headers=[]
            for key,val in pre_def_columns_completed.items():
                data.append(val)
                headers.append(key)
            data_frame = pd.DataFrame(data=[data], columns=headers)
            return data_frame






    def get_dfs_branches(self, tree,level=0, branch=None):
        branches = list()

        #in case it's the leaf value
        if type(tree) is not dict and type(tree) is not list:
            branch.append(tree)
            return branch

        else:
            for key,val in tree.items():
                if level == 0:
                    branch = list()
                    branch.append(key)
                    branches = branches + self.get_dfs_branches(tree=val, level=level+1, branch=branch)
                elif key == 'leaf':
                    for leaf in val:
                        tmp_branch = branch.copy()
                        branches.append(self.get_dfs_branches(tree=leaf, branch=tmp_branch))
                        return branches
                else:
                    tmp_branch = branch.copy()
                    tmp_branch.append(key)
                    branches = branches + self.get_dfs_branches(tree=val, level=level+1, branch=tmp_branch)

        return branches





def init():
    return WebSiteScarperWorker()


#unit test
def test():
    logging.basicConfig(format='[%(asctime)s -%(levelname)s] (%(processName)-10s) %(message)s')
    dateTimeObj = datetime.now()
    ws_scraper = WebSiteScarperWorker()
    #ws_scraper.work({'params':{"service_name":"AWS bla"},'payload':{'scrap_flow':'../awsapiactionurl_scrap_flow.yml', 'url_to_scrap':'https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonappflow.html'}})
    #ws_scraper.work({'params': {}, 'payload': {'scrap_flow': '../aws_iam_services_scraper.yml','url_to_scrap': 'https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_aws-services-that-work-with-iam.html'}})
    ws_scraper.work({'params': {'worker_driver': 'WebSitesScrapingWorker', 'title': 'adHoc'}, 'payload': {'scrap_flow': 'scraper_flows/azure_root_url_scrap.yml', 'url_to_scrap': 'https://docs.microsoft.com/en-us/rest/api/?view=Azure'}})



def print_help():
    title = '''
======================================================================================
=  ====  ====  =========  ======      ================================================
=  ====  ====  =========  =====  ====  ===============================================
=  ====  ====  =========  =====  ====  ===============================================
=  ====  ====  ===   ===  ======  ========   ===  =   ====   ===    ====   ===  =   ==
=   ==    ==  ===  =  ==    ======  =====  =  ==    =  ==  =  ==  =  ==  =  ==    =  =
==  ==    ==  ===     ==  =  =======  ===  =====  ==========  ==  =  ==     ==  ======
==  ==    ==  ===  =====  =  ==  ====  ==  =====  ========    ==    ===  =====  ======
===    ==    ====  =  ==  =  ==  ====  ==  =  ==  =======  =  ==  =====  =  ==  ======
====  ====  ======   ===    ====      ====   ===  ========    ==  ======   ===  ======
======================================================================================

'''

    text = (
        'Version- {} \n\n'
        'Welcome To Web Scraper\n'
        'Using this generic scraper you can define your own web scraping flow \n'
        'Scraping flow based on yaml file that described the flow of scraping'
        '\n'.format(VERSION)
    )

    print(prep_title(title))
    print(
        '-------------------------------------------------------------------------------------------------------------------------------------------------------')
    print(prep_text(text))


if __name__ == '__main__':

    #TODO - Work on desc for params
    parser = argparse.ArgumentParser(description='', usage=print_help())
    parser.add_argument('--logLevel', required=False, type=str, default="INFO")
    parser.add_argument('--scrapFlow', required=True, type=str, default=None)
    parser.add_argument('--urlToScrap', required=True, type=str, default=None)
    parser.add_argument('--title', required=False, type=str, default="ad hoc title")

    args = parser.parse_args()

    logging.basicConfig(format='[%(asctime)s -%(levelname)s] (%(processName)-10s) %(message)s')

    log_level = args.logLevel
    logging.getLogger().setLevel(log_level)

    if args.scrapFlow and args.urlToScrap:
        ws_scraper = WebSiteScarperWorker()
        ws_scraper.work({'params': {"title": args.title},
                         'payload': {'scrap_flow': args.scrapFlow,
                                     'url_to_scrap': args.urlToScrap}})





