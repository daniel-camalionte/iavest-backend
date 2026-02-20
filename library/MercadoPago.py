from library.MySql import MySql
from library.MongoDB import MongoDB

import config.env as memory
import mercadopago
import json
import time

class MercadoPagoApi:
    
    def __init__(self):
        self.mysql = MySql()
        self.curr = self.mysql.open()
        self.mp = mercadopago.MP(memory.mercadopago["CLIENT_ID"], memory.mercadopago["CLIENT_SECRET"])
        self.mongo = MongoDB()
        self.mongo_curr = self.mongo.open()
    
    def get_payment(self, id, consulta=None):
        ret = {}
        
        id = str(id)

        paymentInfo = self.mp.get_payment(id)
        json_texto = json.dumps(paymentInfo, indent=4)
        
        if paymentInfo["status"] == 200:
            order_id = ""
            external_reference = paymentInfo['response']['external_reference'] if 'external_reference' in json_texto else ''
            payment_type_id = paymentInfo['response']['payment_type_id'] if 'payment_type_id' in json_texto else ''

            #transferencia bancária
            #if payment_type_id != 'bank_transfer':
            #    order_id = paymentInfo['response']['order']['id'] if 'order' in json_texto else ''

            type_number = paymentInfo['response']['card']['cardholder']['identification']['type'] if 'cardholder' in json_texto else ''
            number = paymentInfo['response']['card']['cardholder']['identification']['number'] if 'cardholder' in json_texto else ''
            name = paymentInfo['response']['card']['cardholder']['name'] if 'cardholder' in json_texto else ''
            date_created = paymentInfo['response']['card']['date_created'] if 'cardholder' in json_texto else ''
            date_last_updated = paymentInfo['response']['card']['date_last_updated'] if 'cardholder' in json_texto else ''
            first_six_digits = paymentInfo['response']['card']['first_six_digits'] if 'cardholder' in json_texto else ''
            last_four_digits = paymentInfo['response']['card']['last_four_digits'] if 'cardholder' in json_texto else ''
            expiration_month = paymentInfo['response']['card']['expiration_month'] if 'cardholder' in json_texto else ''
            expiration_year = paymentInfo['response']['card']['expiration_year'] if 'cardholder' in json_texto else ''
            collector_id = paymentInfo['response']['collector_id'] if 'collector_id' in json_texto else ''
            description = paymentInfo['response']['description'] if 'description' in json_texto else ''
            id_mp = paymentInfo['response']['id'] 
            money_release_date = paymentInfo['response']['money_release_date'] if 'money_release_date' in json_texto else ''
            #order_id = paymentInfo['response']['order']['id'] if 'order' in json_texto else ''
            player_email = paymentInfo['response']['payer']['email'] if 'email' in json_texto else ''
            player_id = paymentInfo['response']['payer']['id'] if 'payer' in json_texto else ''
            phone_area_code = paymentInfo['response']['payer']['phone']['area_code'] if 'area_code' in json_texto else ''
            phone_number = paymentInfo['response']['payer']['phone']['number'] if 'area_code' in json_texto else ''
            payment_method_id = paymentInfo['response']['payment_method_id'] if 'payment_method_id' in json_texto else ''
            payment_type_id = paymentInfo['response']['payment_type_id'] if 'payment_type_id' in json_texto else ''
            statement_descriptor = paymentInfo['response']['statement_descriptor'] if 'statement_descriptor' in json_texto else ''
            status = paymentInfo['response']['status'] if 'status' in json_texto else ''
            status_detail = paymentInfo['response']['status_detail'] if 'status_detail' in json_texto else ''
            installment_amount = paymentInfo['response']['transaction_details']['installment_amount'] if 'installment_amount' in json_texto else ''
            net_received_amount = paymentInfo['response']['transaction_details']['net_received_amount'] if 'net_received_amount' in json_texto else ''
            total_paid_amount = paymentInfo['response']['transaction_details']['total_paid_amount'] if 'total_paid_amount' in json_texto else ''

            ret['external_reference'] = external_reference
            ret['id_mp'] = id_mp
            ret['type_number'] = type_number
            ret['number'] = number
            ret['name'] = name
            ret['player_email'] = player_email
            ret['player_id'] = player_id
            ret['phone_area_code'] = phone_area_code
            ret['phone_number'] = phone_number
            ret['statement_descriptor'] = statement_descriptor
            ret['payment_method_id'] = payment_method_id
            ret['payment_type_id'] = payment_type_id
            ret['first_six_digits'] = first_six_digits
            ret['last_four_digits'] = last_four_digits
            ret['expiration_month'] = expiration_month
            ret['expiration_year'] = expiration_year
            ret['collector_id'] = collector_id
            ret['description'] = description
            ret['order_id'] = order_id
            ret['installment_amount'] = installment_amount
            ret['net_received_amount'] = net_received_amount
            ret['total_paid_amount'] = total_paid_amount
            ret['status'] = status
            ret['status_detail'] = status_detail
            ret['date_created'] = date_created    
            ret['date_last_updated'] = date_last_updated
            ret['money_release_date'] = money_release_date
            ret['data'] = int(time.time())

            #armazenando log no mongo
            if not consulta:
                collection = self.mongo_curr["mercado_pago_payment"]
                collection.insert_one(paymentInfo)
                collection.close
            
            return ret
        else:
            return None
    
    def __del__(self):
        self.curr.close()
        self.mysql.close()