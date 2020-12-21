#!/usr/bin/python3.7
# -*- coding: utf-8 -*-

import re
import datetime
import mysql.connector
import json, tango
from tango import Database, DbDevInfo, DeviceProxy, DeviceAttribute, AttributeProxy, EventType, DeviceData

class HDBPP():
    """
    Класс HDBPP используется для упрвления сервером архивацией и получения 
    истории архивирования атрибутов устройств tangoю
    
    Note:
        По умолчанию заданны настройки для работы на дистрибутиве TangoBox 9.3
    
    Attributes
    ----------
    host: str
        ip адрес базы сервера истории(СИ)
    user: str
        имя пользователя для подключения к СИ
    password: str
        пароль пользователя для подключения к СИ
    database: str
        имя базы на СИ, где хранится история
    archive_server_name: str
        имя Device Server-а tango(сервера архивации(СА)), который записывает историю
    server_default: str
        адрес сервера на котором работают архивируемые Device Server-а
        
    Methods
    -------
    attr_set_server(attr)
        Добавляет к атрибуту адрес сервера на котором он работает
    connect()
        Подключиться к СИ и СА
    connect_to_hdbpp()
        Подключиться к СИ
    connect_to_archive_server()
        Подключиться к СА
    close()
        Отключиться от СИ
    get_att_conf(attr)
        Получить информацию об атрибуте с СИ
    get_data_type(att_conf_data_type_id)
        Получить тип атрибута
    get_archive(attr, date_from, date_to)
        Получить историю сохрания атрибута
    archiving_add(attrs)
        Добавить атрибуты на СА
    archiving_pause(attr)
        Поставить на паузу арихирование атрибута
    archiving_remove(attr)
        Удалить атрибут с СА
    archiving_start(attr)
        Начать архивирование атрибута
    archiving_status(attr)
        Статус архивирования атрибута
    archiving_stop(attr)
        Остановить архивирование атрибута
    archiving_set_strategy(attr, strategy)
        Установить стратегию архивирования атрибута
    archiving_set_ttl(attr, ttl)
        Установить кол-во дней архивирования атрибута
    archiving_get_strategy(attr)
        Получить стратегию архивирования атрибута
    archiving_get_ttl(attr)
        Получить кол-во дней архивирования атрибута
    attr_is_archiving(attr)
        Узнать архивируется ли атрибут.
    attr_set_period(attr, period, archive_period, archive_abs_change, archive_rel_change)
        Установка параметров архивирования атрибута.
    def attr_get_period(attr)
        Получение параметров архивирования атрибута.
    """
    
    def __init__(self, host="172.18.0.7", user="root", password="tango", database="hdbpp", 
                        archive_server_name="archiving/hdbpp/eventsubscriber.1",
                        server_default = "tango://tangobox:10000"):
        """
        Конструктор класса. Устанавливаем все необходимые атрибуты для объекта HDBPP
        
        Parameters
        ----------
        host: str
            ip адрес базы сервера истории(СИ)
        user: str
            имя пользователя для подключения к СИ
        password: str
            пароль пользователя для подключения к СИ
        database: str
            имя базы на СИ, где хранится история
        archive_server_name: str
            имя Device Server-а tango(сервера архивации(СА)), который записывает историю
        server_default: str
            адрес сервера на котором работают архивируемые Device Server-а
        """
        
        self.cnx = None
        self.archive_server = None
        
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.archive_server_name = archive_server_name
        
        # "tango://tangobox:10000" сервер по умолчанию, на котором работают наши сервера
        self.server_default = server_default
        
    def __del__(self):
        """
        Деструктор класса. Закрываем соединения, если забыли это сделать.
        """
        
        if self.cnx :
            self.close()
                    
    # Если у атрибута не указан сервер на котором он работает, до добавляем сервер по умолчанию.
    def attr_set_server(self, attr):
        """
        Добавляем к атрибуту адрес сервер на котором он работает, если сервер не указан. 
        
        Parameters
        ----------
        attr: str
            имя атрибута
            
        Returns
        -------
        str
            адрес и имя атриба, например tango://tangobox:10000/ECG/ecg/1/Lead
        """
        
        if "tango://" in attr :
            return attr
        
        if (attr[0] != '/') :
            attr = '/' + attr
        
        return self.server_default + attr
    
    def connect(self):
        """
        Подключиться к СИ и СА
            
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        if self.connect_to_hdbpp() == False :
            return False
        
        if self.connect_to_archive_server() == False :
            return False
        
        return True
    
    def connect_to_hdbpp(self):
        """
        Подключиться к СИ
            
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        try:
            self.cnx = mysql.connector.connect(host = self.host, user = self.user, password = self.password, database = self.database)
        except mysql.connector.Error as err:
            print("[error]: connect to {}: {}".format(self.database, err))
            return False

        return True
    
    def connect_to_archive_server(self):
        """
        Подключиться к СА
            
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        try:
            self.archive_server = DeviceProxy(self.archive_server_name)
        except DevFailed as err:
            print("[error]: Failed to create proxy to {}: {}".format(self.archive_server_name, err))
            return False
        
        return True
    
    def close(self):
        """
        Закрыть соединение с СИ.
        """
        
        if self.cnx :
            self.cnx.close()
            self.cnx = None
        
    def get_att_conf(self, attr):
        """
        Получить информацию об атрибуте с СИ. Необходима для взятия архива.
        
        Parameters
        ----------
        attr: str
            имя атрибута
            
        Returns
        -------
        arr
            Массив с информацией об устройстве с СИ. Поля из таблицы att_conf
        None
            в случае ошибки
        """
        
        attr = self.attr_set_server(attr)
        
        cursor = self.cnx.cursor()
        
        sql = "SELECT * FROM att_conf WHERE att_name RLIKE '{0}' LIMIT 0,1".format(attr)

        cursor.execute(sql)
                
        result = cursor.fetchall()

        if len(result) == 0 :
            return None
        else :
            return result[0]
        
    def get_data_type(self, att_conf_data_type_id):
        """
        Получить строковый тип данных атрибута, по числовому идентификатору типа данных.
        
        Parameters
        ----------
        att_conf_data_type_id: int
            тип данных атрибута
            
        Returns
        -------
        str
            строковый тип данных атрибута, например scalar_devushort_ro
        None
            в случае ошибки
        """
        
        cursor = self.cnx.cursor()
        
        sql = "SELECT data_type FROM att_conf_data_type WHERE att_conf_data_type_id = {0} LIMIT 0,1".format(att_conf_data_type_id)
        cursor.execute(sql)
                
        result = cursor.fetchall()
        
        if len(result) == 0 :
            return None
        else :
            return result[0]
               
    def get_archive(self, attr, date_from = None, date_to = None):
        """
        Получить историю сохранения атрибута.
        
        Note:
            С параметрами по умолчанию берет историю за все время
        
        Parameters
        ----------
        attr: str
            имя атрибута
        date_from: datetime
            дата с которой взять историю
        date_to: datetime
            дата по которую взять историю
        
        Returns
        -------
        array
            архив значений
        None
            в случае ошибки
        """
        
        attr = self.attr_set_server(attr)
        
        att_conf_id = 0
        att_conf_data_type_id = 0
        table = ''
        
        # Если (date_from && date_to) == None, то берем данные за все время
        # Время до которого берем данные
        if date_to == None :
            # По умолчанию до текущего времени
            date_to = datetime.datetime.now()
        
        # Время от которого берем данные
        if date_from == None :
            # По умолчанию все данные
            date_from = datetime.datetime(1, 1, 1, 0, 0, 0) 
            
        result = hdbpp.get_att_conf(attr)
        if result :
            att_conf_id = result[0]
            att_conf_data_type_id = result[2]
        else:
            return None
        
        # Получаем тип данных, по нему узнаем в какой таблице хранится история.
        result = self.get_data_type(att_conf_data_type_id)
        if result :
            table = "att_" + str(result[0])
        else:
            return None
        
        cursor = self.cnx.cursor()
        sql = "SELECT * FROM {0} WHERE att_conf_id = {1} and (insert_time >= '{2}' and insert_time <= '{3}')".format(table, att_conf_id, date_from, date_to)
        
        cursor.execute(sql)
                
        result = cursor.fetchall()
        if len(result) == 0 :
            return None
        else :
            return result
    
    def archiving_add(self, attrs):
        """
        Добавить атрибуты на СА. Необходимо сделать если его нет.
        
        Parameters
        ----------
        attrs: array(str)
            массив имен атрибутов
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        for i, a in enumerate(attrs):
            attrs[i] = self.attr_set_server(attrs[i])
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevVarStringArray, attrs)
        try:
            self.archive_server.command_inout("AttributeAdd", argIn)
            return True
        except tango.DevFailed as df:
            return False
    
    def archiving_pause(self, attr):
        """
        Поставить на паузу арихирование атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            self.archive_server.command_inout("AttributePause", argIn)
            return True
        except tango.DevFailed as df:
            return False
    
    def archiving_remove(self, attr):
        """
        Удалить атрибут с СА.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            self.archive_server.command_inout("AttributeRemove", argIn)
            return True
        except tango.DevFailed as df:
            return False
    
    def archiving_start(self, attr, period = 0, archive_period = None, archive_abs_change = None, archive_rel_change = None):
        """
        Начать архивирование атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        # Если было передано короткое имя атрибута, то преобразуем его в полное
        # 'tango://tangobox:10000/ECG/ecg/1/Lead'
        attr = self.attr_set_server(attr)
        
        # Полное имя преобразуем в короткое
        # 'ECG/ecg/1/Lead'
        sp = attr.split('/')
        attr_short = sp[-4] + "/" + sp[-3] + "/" + sp[-2] + "/" + sp[-1]
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            self.attr_set_period(attr_short, period, archive_period, archive_abs_change, archive_rel_change)
            self.archive_server.command_inout("AttributeStart", argIn)
            return True
        except tango.DevFailed as df:
            return False
    
    def archiving_status(self, attr):
        """
        Статус архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        status = {}
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            ret = self.archive_server.command_inout("AttributeStatus", argIn)
        except tango.DevFailed as df:
            status["Archiving"] = False
            return status
        
        # Преобразуем возвращаемую строку статсусов к словарю статусов
        ret = ret.split("\n")
        for r in ret:
            r = re.sub(' +', ' ', r)
            r = r.split(":")
            status[r[0].lstrip().rstrip()] = r[1].lstrip().rstrip()
            
        return status
        
    def archiving_stop(self, attr):
        """
        Остановить архивирование атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            self.archive_server.command_inout("AttributeStop", argIn)
            return True
        except tango.DevFailed as df:
            return False
    
    def archiving_set_strategy(self, attr, strategy = "ALWAYS"):
        """
        Установить стратегию архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        strategy: str
            всегда ALWAYS, других стратегий нет
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevVarStringArray, [attr, str(strategy)])
        try:
            self.archive_server.command_inout("SetAttributeStrategy", argIn)
            return True
        except tango.DevFailed as df:
            return False
    
    def archiving_set_ttl(self, attr, ttl):
        """
        Установить кол-во дней архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        ttl: int/str
            кол-во дней
        
        Returns
        -------
        bool
           True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevVarStringArray, [attr, str(ttl)])
        try:
            self.archive_server.command_inout("SetAttributeTTL", argIn)
            return True
        except tango.DevFailed as df:
            return False
        
    def archiving_get_strategy(self, attr):
        """
        Получить стратегию архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True в случае успеха, иначе False
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            return self.archive_server.command_inout("GetAttributeStrategy", argIn)
        except tango.DevFailed as df:
            return False
        
    def archiving_get_ttl(self, attr):
        """
        Получить кол-во дней архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        int
            кол-во дней архивирования
        bool
            False в случае ошибки
        """
        
        attr = self.attr_set_server(attr)
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevString, attr)
        try:
            return self.archive_server.command_inout("GetAttributeTTL", argIn)
        except tango.DevFailed as df:
            return False
    
    def attr_is_archiving(self, attr):
        """
        Узнать архивируется ли атрибут.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        bool
            True если да, иначе False
        """
        
        ret = self.archiving_status(attr)
        
        if ret["Archiving"] == "Started":
            return True
        
        return False
    
    def attr_set_period(self, attr, period = 0, archive_period = None, archive_abs_change = None, archive_rel_change = None):
        """
        Установка параметров архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        period: int
            миллисекунды
        archive_period: str
            миллисекунды, если превышен порог изменеия атрибута
        archive_abs_change: str
            порог изменения атрибута в еденицах
        archive_rel_change: str
            порог изменения атрибута в процентах
        """
        
        ap = AttributeProxy(attr)
            
        if (period > 0) :
            ap.poll(period)                
        else :
            if (ap.is_polled()) :
                ap.stop_poll(attr)
            
        attr_conf = ap.get_config()
                
        attr_conf.events.arch_event.archive_period = archive_period
        attr_conf.events.arch_event.archive_abs_change = archive_abs_change
        attr_conf.events.arch_event.archive_rel_change = archive_rel_change
            
        ap.set_config(attr_conf)
        
    def attr_get_period(self, attr):
        """
        Получение параметров архивирования атрибута.
        
        Parameters
        ----------
        attr: str
            имя атрибута
        
        Returns
        -------
        dict
            Параметры архивирования
        """
       
        ap = AttributeProxy(attr)
            
        d = {}
        arch_event = {}
            
        period = ap.get_poll_period()
        a = ap.get_config()
            
        arch_event["archive_period"] = a.events.arch_event.archive_period
        arch_event["archive_abs_change"] = a.events.arch_event.archive_abs_change
        arch_event["archive_rel_change"] = a.events.arch_event.archive_rel_change
        arch_event["poll_period"] = period
        
        return arch_event
        
if __name__ == '__main__':
    hdbpp = HDBPP()
    
    if hdbpp.connect() == False :
        exit(0)
    
    archive = hdbpp.get_archive('tango://tangobox:10000/ECG/ecg/1/Lead')
    #if archive :
    #    for a in archive :
    #        print(a[4])
    
    #hdbpp.archiving_add(['tango://tangobox:10000/ECG/ecg/1/Lead'])
    
    #ret = hdbpp.archiving_status('tango://tangobox:10000/ECG/ecg/1/Lead')
    #print(ret)
    
    #ret = hdbpp.archiving_status('tango://tangobox:10000/ECG/ecg/1/Lead')
    #print(ret)
    
    #ret = hdbpp.archiving_status('tango://tangobox:10000/ECG/ecg/1/Gain')
    #print(ret)

    hdbpp.close()
    