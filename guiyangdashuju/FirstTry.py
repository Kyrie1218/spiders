#-*- coding: utf-8 -*-
import xml.etree.ElementTree as etree
import os
import requests
import json
import time
import logging
import re
import MongoDB
import Redownload

class CrawlError(Exception): pass

class Download(object):
    def __init__(self,config_file,record_file):
        self.config_logging()
        if self.record_file_exists(record_file):
            print('doub')
            redownload = Redownload()

        else:
            orders = self.parse_config_file(config_file)

            orders_after_download_ent_list = self.download_enterprise_list(orders)
            self.write_to_json_file(record_file, orders_after_download_ent_list)

            orders_after_download_ent_info = self.download_ent_info_and_write2db(orders_after_download_ent_list,'贵阳大数据')
            self.write_to_json_file(record_file,orders_after_download_ent_info)

    def config_logging(self):
        # 在日志文件中记录信息
        root_logger= logging.getLogger()
        root_logger.setLevel(logging.WARNING) # or whatever
        handler = logging.FileHandler('download.log', 'w', 'utf-8') # or whatever
        formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s') # or whatever
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        # 在控制台输出日志信息
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        formatter = logging.Formatter('%(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    def record_file_exists(self, record_file):
        return True if os.path.exists(record_file) else False

    def parse_config_file(self, config_file):
        # 解析xml配置文件，并且获取订单的状态
        tree = etree.parse(config_file)
        root = tree.getroot()
        list_of_order_status = []
        orders = []
        dir_name = '全部订单的企业列表'
        if not os.path.exists(dir_name):
            os.mkdir(dir_name) # 创建目录
        for each in root:
            order_id = each.find('order_id').text
            token_id = each.find('token_id').text
            tag = each.tag
            ent_list_url = each.find('enterprist_list/url').text
            ent_list_filename = dir_name + '/' + tag + '-' +each.find('enterprist_list/file_name').text
            ent_info_url = each.find('enterprist_info/url').text
            ent_info_dirname = each.find('enterprist_info/dir').text

            order_status = self.get_total_count_of_order(token_id, ent_list_url, ent_list_filename, tag)
            # order_status = self.download_enterprise_list(token_id, ent_list_url, ent_list_filename, tag, record_file)
            # list_of_order_status.append(order_status)
            time.sleep(2)

            order = {
                'order_id': order_id,
                'token_id': token_id,
                'tag': tag,
                'ent_list_url' : ent_list_url,
                'ent_list_filename' : ent_list_filename,
                'ent_info_url' : ent_info_url,
                'ent_info_dirname':ent_info_dirname,
                # 'total_count': order_status['total'],
                'order_status': order_status
            }
            orders.append(order)
        return orders

    def write_to_json_file(self, record_file, orders):
        with open(record_file, 'w', encoding='utf-8') as file:
            list_of_order_status = []
            for each in orders:
                list_of_order_status.append(each['order_status'])
            json.dump(list_of_order_status, file,ensure_ascii=False, indent=2)

    def get_total_count_of_order(self, token_id, ent_list_url, ent_list_filename, tag_name):
        # 获取每个订单里的数据量
        # logging.info('正在查询订单：{}'.format(tag_name))
        logging.warning('正在查询订单：{}'.format(tag_name))
        para = {
            'tokenId': token_id
        }
        response = requests.post(ent_list_url, params=para)
        content = json.loads(response.text)
        if content['rescode'] != '00000': # 如果在返回结果中rescode的值不为00000，则说明返回的结果错误
            order = {'order_name':tag_name}
            logging.error('查询有错误，错误信息如下：{}'.format(content))
            status = {'tag':tag_name, 'ent_list_filename':ent_list_filename,'get_ent_list':0, 'total':0, 'saved':0}
            return status

        total_count = json.loads(content['encryptdata'])['total']
        # logging.info('查询到一共有{}条数据'.format(total_count))
        logging.warning('查询到一共有{}条数据'.format(total_count))
        status = {'tag':tag_name, 'ent_list_filename':ent_list_filename, 'get_ent_list':0, 'total':total_count, 'saved':0}
        return status

    def download_enterprise_list(self, orders):
        for each in orders:
            token_id = each['token_id']
            ent_list_url = each['ent_list_url']
            ent_list_filename = each['ent_list_filename']
            tag = each['tag']
            total_count = each['order_status']['total']

            if total_count == 0:
                continue
            # 因为在服务器端设置了一次查询只能有200条结果，所以只能分批返回查询数据
            logging.warning('正在下载订单的企业列表：{} '.format(tag))
            cycle_times = total_count // 200 + 2
            try:
                for i in range(1,  cycle_times):
                    print('\t正在返回第{}页的结果'.format(i))
                    temp = '\"pageIndex\":\"{}\", \"pageSize\":\"200\"'.format(i)
                    paginator = '{%s}' %temp
                    para = {
                        'tokenId': token_id,
                        'encryptdata': paginator
                    }
                    response = requests.post(ent_list_url, params=para)
                    content = json.loads(response.text)
                    if content['rescode'] != '00000':
                        print('error')
                        logging.error(content)
                        each['order_status']['get_ent_list'] = 1
                        raise CrawlError() # 通过抛出异常来退出最外层循环
                    with open(ent_list_filename, 'a+', encoding='utf-8') as f: # 把结果写入到文件中
                        f.write(str(content))
                    time.sleep(2)
                # logging.info('{}的企业列表信息查询完成！'.format(tag))
                logging.warning('{}的企业列表下载完成！'.format(tag))
                each['order_status']['get_ent_list'] = 1
            except Exception:
                continue

        return orders

    def extract_enterprise_from_file(self, ent_list_filename):
        with open(ent_list_filename, 'r', encoding='utf-8') as file:
            content = file.read()
            result = {}
            ent_id = re.findall('"ent_id":"(\d{0,10})"', content, re.S)
            entname = re.findall('"entname":"(.*?)"', content, re.S)
            for m,n in zip(ent_id, entname):
                result[n] = m  # 格式：'佛山市三水恒昌华泰小额贷款有限公司': '8700178'
        # print('一共有效下载{}条企业信息'.format(len(result)))
        logging.warning('一共有效下载{}条企业信息'.format(len(result)))
        return result

    def download_ent_info_and_write2db(self, orders, db_name):
        db = MongoDB.DataBase(db_name).get_db_handle()

        for each in orders:
            ent_info_dirname = each['ent_info_dirname']
            tag = each['tag']
            token_id = each['token_id']
            ent_list_filename = each['ent_list_filename']
            ent_info_url = each['ent_info_url']
            order_status = each['order_status']
            success_count = 0

            try:
                if order_status['get_ent_list'] == 0: # 跳过企业列表下载失败的订单
                    continue
                all_enterprise = self.extract_enterprise_from_file(ent_list_filename)
                logging.warning('正在查询全部企业的详细信息')
                db_sheet = db[tag + '-' + ent_info_dirname] # 构造Mongodb中的数据表

                for ent_name, ent_id in all_enterprise.items():
                    temp = '\"organizationid\":\"{}\"'.format(ent_id)
                    parameters = '{%s}' %temp  #例子：parameters = "{\"organizationid\":\"5115801\"}"
                    para = {
                        'tokenId': token_id,
                        'encryptdata': parameters
                    }
                    response = requests.post(ent_info_url, params=para)
                    content = json.loads(response.text)
                    if content['rescode'] != '00000':
                        logging.error('存在错误，下载失败：{}'.format(content))
                        raise CrawlError()
                    # print(content)
                    print('正在写入数据库：{}'.format(ent_name))
                    db_sheet.insert_one({'ent_name':ent_name, 'info':str(content)})
                    success_count += 1
                    time.sleep(1.5)
                else:
                    order_status['saved'] = success_count

            except Exception as e:
                order_status['saved'] = success_count
                logging.error(e)
                continue
        return orders


    def parse_record_file(self, record_file):
        with open(record_file, 'r', encoding='utf-8') as file:
            list_of_order_status = json.load(file)
            print(list_of_order_status)
        return list_of_order_status

    def parse_record_file(self, record_file):
        with open(record_file, 'r', encoding='utf-8') as file:
            list_of_order_status = json.load(file)
            print(list_of_order_status)
        return list_of_order_status

    def check_order_status(self, list_of_order_status):
        for each in list_of_order_status:
            tag = each['tag']
            saved = each['saved']
            total = each['total']
            get_ent_list = each['get_ent_list']
            ent_list_filename = each['ent_list_filename']

            if get_ent_list and saved != total:
                # 企业详细信息没有下载完毕
                all_enterprise = self.extract_enterprise_from_file(ent_list_filename)
                redownload_enterprise = all_enterprise[saved:]
                self.download_ent_info_and_write2db()

if __name__ == '__main__':
    test = Download()