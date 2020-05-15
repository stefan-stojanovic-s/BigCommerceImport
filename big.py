import requests
import sqlite3
import zeep
from time import sleep
from config import COMTRADE_USERNAME,COMTRADE_PASSWORD,CLIENT_ID,TOKEN_ID,STORE_HASH

class Logs():
    logs=[]
    
    @staticmethod
    def log(message):
        with open('logs/logs.txt','a',encoding='utf8') as f:
            f.writelines(message + '\n')

        with open('logs/last.log','a',encoding='utf8') as f:
            f.writelines(message + '\n')
    
    @staticmethod
    def get_log():
        return Logs.logs


class BigCommerceAuto:
    def __init__(self):
        self.comtrade_url='http://www.ct4partners.ba/webservices/ctproductsinstock.asmx?WSDL'
        self.headers={
           'accept': "application/json",
           'X-Auth-Client':'{}'.format(CLIENT_ID),
           'X-Auth-Token':'{}'.format(TOKEN_ID) 
           } 
        self.big_url=f'https://api.bigcommerce.com/stores/{STORE_HASH}/v3/'
        self.category_url=f'{self.big_url}catalog/categories'
        self.product_url=f'{self.big_url}catalog/products'
        self.client=zeep.Client(self.comtrade_url)

    def add_to_db(self,id,name):
        conn=sqlite3.connect('products.db')
        cursor=conn.cursor()
        cursor.execute('SELECT * FROM products WHERE id =? AND name=?',(id,name))
        if cursor.fetchone() == None:
            cursor.execute('INSERT INTO products VALUES (?,?)',(id,name))
            conn.commit()
            conn.close()
        
    def find_in_db(self,name):
        conn=sqlite3.connect('products.db')
        cursor=conn.cursor()
        cursor.execute('SELECT * FROM products WHERE name=?',(name,))
        result=cursor.fetchone()
        if result != None:
            conn.close()
            return result
        else:
            conn.close()
            return None

    def export_comtrade_products(self):
        Logs.log("Getting products from ComTrade ...")
        comtrade_request=self.client.service.GetCTProducts_WithAttributes(COMTRADE_USERNAME,COMTRADE_PASSWORD)
        Logs.log("Products gotten, checking")
        return comtrade_request

    def export_comtrade_categories(self):
        Logs.log('Getting categories from ComTrade ...')
        #these 2 should be enabled in the final version
        comtrade_request=self.client.service.GetCTProductGroups(COMTRADE_USERNAME,COMTRADE_PASSWORD)
        return comtrade_request

    def export_big_products(self):
        exported=[]
        i=2;
        #There is no other way of retriving > 250 products then like this bellow
        all_products=requests.get(self.product_url+'?limit=250',headers=self.headers)
        response=all_products.json()
        page_number=int(response['meta']['pagination']['total_pages'])
        exported.extend(response['data'])
        if page_number == 1:
            return exported
        else:
            while i <= page_number:
                r=requests.get(self.product_url+'?limit=250&page='+str(i),headers=self.headers)
                res=r.json()
                exported.extend(res['data'])
                i+=1; 
        for product in exported:
            Logs.log("Dodajem u bazu {}".format(product['name']))
            self.add_to_db(product['id'],product['name'])
    
    def export_big_categories(self):
        exported=[]
        i=2
        #There is no other way of retriving > 250 categories then like this bellow
        all_categories=requests.get(self.category_url+'?limit=250',headers=self.headers)
        response=all_categories.json()
        page_number=int(response['meta']['pagination']['total_pages'])
        exported.extend(response['data'])
        if page_number == 1:
            return exported
        else:
            while i <= page_number:
                r=requests.get(self.category_url+'?limit=250&page='+str(i),headers=self.headers)
                res=r.json()
                exported.extend(res['data'])
                i+=1;
        return exported
            

    def import_big_custom_fields(self,product_id,data):
        r=requests.post('{}/{}/custom-fields'.format(self.product_url,product_id),headers=self.headers,data=json.dumps(data))
        response=r.json()['data']
        if r.status_code == 200:
            Logs.log("Dodati novi atributi za {}".format(response['name']))
        else:
            Logs.log(r.text)

    def import_big_products(self):
        categories=self.export_big_categories()
        self.export_big_products()
        DATA=self.export_comtrade_products()
        for x in DATA:  #self.export_comtrade_products instead of DATA    
            custom_fields=[]
            images=[]
            update=False
            body={
                'name':x['NAME'],
                'sku':x['CODE'].replace(' ','-'),
                'description':x['SHORT_DESCRIPTION'],
                'brand_name':x['MANUFACTURER'],
                'weight':1,
                'upc':x['BARCODE'] ,
                'type':'physical',
                'price':float(x['PRICE'].replace(',','.')),
                'retail_price':float(x['RETAILPRICE'].replace(',','.')),
                'warranty':x['WARRANTY']
            }
            #upc cant be null so we check
            if body['upc'] == None:
                body['upc']=''
            
            #not to put them in body if there are not any, and if there 
            #are go through them and append them
            if x['IMAGE_URLS'] != None and x['IMAGE_URLS']['URL'][0] !=None:
                images.extend([{'image_url':image.replace(' ','%20')} for image in x['IMAGE_URLS']['URL']])
                images[0]['is_thumbnail']=True
                body['images']=images

            #going through the attributes etc. options_values
            if x['ATTRIBUTES'] != None:
                for attr in x['ATTRIBUTES']['ATTRIBUTE']: 
                    #if attr name is None
                    if attr['AttributeName'] == None:
                        attr['AttributeName']=attr['AttributeCode']
                    # if attr value is None
                    if attr['AttributeValue'] == None:
                        attr['AttributeValue']='No value'
                    
                    custom_fields.append({
                        'name':attr['AttributeName'],
                        'value':attr['AttributeValue'] })

                body['custom_fields']=custom_fields

            #adding a category
            for cat in categories:  
                if x['PRODUCTGROUPCODE'] in cat['name']:
                    #body['categories'] = [cat['id']]
                    body['categories'] = [cat['id']]
                    break

            #checking if it exists in products, if it does just update
            up_product=self.find_in_db(body['name'])
            if up_product:
                r=requests.get('{}/{}'.format(self.product_url,up_product[0]),headers=self.headers)
                if r.status_code==200:
                    response=r.json()
                    up_product=response['data']
                    update=True
                    up_product['name']=body['name']
                    up_product['sku']=body['sku']
                    up_product['description']=body['description']
                    up_product['warranty']=body['warranty']
                    up_product['upc']=body['upc']
                    up_product['price']=body['price']
                    up_product['retail_price']=body['retail_price']

                    if 'images' in body:
                        up_product['images']=body['images']

                    if 'custom_fields' in body:
                        #checking if it has any if not, we will add custom_fields
                        #like this we update
                        r=requests.get('{}/{}/custom-fields'.format(self.product_url,up_product['id']),headers=self.headers)
                        response=r.json()
                        data=response['data']        
                        """
                        Checking for custom fields eg. attributes :
                        1. if they are the same length
                        2.if there are more in a comtrade response then in a product
                        3. if there is no custom_fields on product but there are in comtrade response
                        """ 
                        if data and len(data) == len(custom_fields):
                            for a,b in zip(data,custom_fields):
                                if a['value'] in b['value']:
                                    continue
                                else:
                                    a['value']=b['value']
                                    r=requests.put('{}/{}/custom-fields/{}'.format(self.product_url,up_product['id'],a['id']),headers=self.headers,data=json.dumps(a))
                                    if r.status_code==200:
                                        Logs.log('Attribute updated')

                        elif data and len(data) < len(custom_fields):
                            check_data=[{'name':a['name'],'value':a['value']} for a in data ]
                            diff=[a for a in custom_fields if a not in check_data]
                            for diffrence in diff:
                                self.import_big_custom_fields(up_product['id'],diffrence)
                        
                        elif not data:
                            for check in custom_fields:
                                self.import_big_custom_fields(up_product['id'],check)
                    
                    body=up_product
                else:
                    print(r.text)         
            #if they are the same just update
            if update:
                a=requests.put('{}/{}'.format(self.product_url,str(body['id'])),headers=self.headers,data=json.dumps(body))
                if a.status_code==200:
                    Logs.log('Produkt {} uspesno azuriran'.format(body['name']))
                else:
                    Logs.log('Produkt {} nije uspesno azuriran'.format(body['name']))
                    Logs.log(a.text)
            else:
                a=requests.post(self.product_url,headers=self.headers,data=json.dumps(body))
                if a.status_code==200:
                    Logs.log('Produkt {} je uspesno kreiran'.format(body['name']))
                elif a.status_code == 409:
                    Logs.log('Produkt {} je duplikat'.format(body['name']))
                else:
                    Logs.log('Produkt {} je nije uspesno kreiran'.format(body['name']))
                    Logs.log(a.text)

            
            

    def import_big_categories(self):
        PRODUCT_GROUP=self.export_comtrade_categories()
        body={
            'name':'',
            'description':'',
            'parent_id':0
            }
        for x in PRODUCT_GROUP:
            body['name']=x['Code']
            body['description']=x['GroupDescription']
            a=requests.post(self.category_url,headers=self.headers,data=json.dumps(body))
            if a.status_code==200:
                Logs.log('{} kategorija uspesno dodata'.format(body['name']))
            else:
                Logs.log('{} vec postoji!'.format(body['name']))

