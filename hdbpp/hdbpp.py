# !/usr/bin/python3
# -*- coding: utf-8 -*-

import re
import datetime
import psycopg2
import mysql.connector
import json, tango
from tango import Database, DbDevInfo, DeviceProxy, DeviceAttribute, AttributeProxy, EventType, DeviceData

class HDBPP():
    """
    The HDBPP class is used to manage the archive server and receive
    archiving history of tango device attributes

    Note:
	The default settings are set to work on the TangoBox 9.3 distribution

    Attributes
    ----------
    dbtype: str
        type of database, "mysql" or "postgresql"
    host: str
         history server base ip address (HS)
    user: str
        username to connect to HS
    password: str
        user password for connecting to HS
    database: str
        the name of the base in HS where the history is stored
    archive_server_name: str
        the name of the tango Device Server (Archive Server (AS)) that records history
    server_default: str
        the address of the server on which the archived Device Servers are running
        
    Methods
    -------
    attr_set_server (attr)
        Adds to the attribute the address of the server it is running on
    connect ()
        Connect to HS and AS
    connect_to_hdbpp ()
        Connect to HS
    connect_to_archive_server ()
        Connect to AS
    close ()
        Disconnect from HS
    get_att_conf (attr)
        Get attribute information from HS
    replace_att_conf(self, data_type, attr)
        Add attribute to HS. Required for archiving. Adds to hdbpp.att_conf
    get_data_type_id(self, data_format, data_type, writable):
        Get numeric data type id by data_format, data_type and writable.
    get_data_type(att_conf_data_type_id)
        Получить тип атрибута
    get_archive (attr, date_from, date_to)
        Get the history of an attribute's persistence
    archiving_add (attrs)
        Add attributes to AS
    archiving_pause (attr)
        Pause attribute archiving
    archiving_remove (attr)
        Remove attribute from AS
    archiving_start (attr, period, archive_period, archive_abs_change, archive_rel_change)
        Start Archiving Attribute
    archiving_status (attr)
        Attribute archiving status
    archiving_stop (attr)
        Stop archiving an attribute
    archiving_set_strategy (attr, strategy)
        Set an attribute archiving strategy
    archiving_set_ttl (attr, ttl)
        Set the number of days to archive an attribute
    archiving_get_strategy (attr)
        Get an Attribute Archiving Strategy
    archiving_get_ttl (attr)
        Get the number of days the attribute was archived
    attr_is_archiving (attr)
        Find out if the attribute is being archived.
    attr_set_period (attr, period, archive_period, archive_abs_change, archive_rel_change)
        Setting the parameters for archiving the attribute.
    attr_get_period (attr)
        Retrieving archive parameters for an attribute.
    """
    
    def __init__(self, dbtype="mysql", host="172.18.0.7", user="tango", password="tango",
			database="hdbpp", archive_server_name="archiving/hdbpp/eventsubscriber.1", 
			server_default="tango://tangobox:10000"):
        """
        Class constructor. Set all the necessary attributes for the HDBPP object
        Parameters
        ----------
        dbtype: str
            type of database, "mysql" or "postgresql"
        host: str
            history server base ip address (HS)
        user: str
            username to connect to HS
        password: str
            user password for connecting to HS
        database: str
            the name of the base in HS where the history is stored
        archive_server_name: str
            the name of the tango Device Server (Archive Server (AS)) that records history
        server_default: str
            the address of the server on which the archived Device Servers are running
        """
        
	self.dbtype = dbtype
        self.cnx = None
        self.archive_server = None
        
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.archive_server_name = archive_server_name
        
        # "tango://tangobox:10000" is the default server that our servers run on
        self.server_default = server_default
        
    def __del__(self):
        """
        Class destructor. Close connections if you forgot to do this.
        """
        
        if self.cnx :
            self.close()
                    
    # If the attribute does not have the server on which it is running, add the default server before.
    def attr_set_server(self, attr):
        """
        Add to the attribute the address of the server on which it works, if the server is not specified.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        str
            the address and name of the attribute, for example tango://tangobox:10000/ECG/ecg/1/Lead
        """
        
        if "tango://" in attr :
            return attr
        
        if (attr[0] != '/') :
            attr = '/' + attr
        
        return self.server_default + attr
    
    def connect(self):
        """
        Connect to HS and AS

        Returns
        -------
        bool
            True if successful, otherwise False
        """
        
        if self.connect_to_hdbpp() == False :
            return False
        
        if self.connect_to_archive_server() == False :
            return False
        
        return True
    
    def connect_to_hdbpp(self):
        """
        Connect to HS

        Returns
        -------
        bool
            True if successful, otherwise False
        """
        
        if self.dbtype == "mysql" :
            try:
                self.cnx = mysql.connector.connect(host=self.host, user=self.user, password=self.password, database=self.database)
            except mysql.connector.Error as err:
                print("[error]: connect to {}: {}".format(self.database, err))
                return False
        elif self.dbtype == "postgresql" :
            try:
                self.cnx = psycopg2.connect(dbname=self.database, user=self.user, password=self.password, host=self.host)
            except OperationalError as err:
                print("[error]: connect to {}: {}".format(self.database, err))
                print_psycopg2_exception(err)
                return False
        else :
            print("[error]: no supported db: {}".format(self.dbtype))
            return False
            
        return True
    
    def connect_to_archive_server(self):
        """
        Connect to AS

        Returns
        -------
        bool
            True if successful, otherwise False
        """
        
        try:
            self.archive_server = DeviceProxy(self.archive_server_name)
        except DevFailed as err:
            print("[error]: Failed to create proxy to {}: {}".format(self.archive_server_name, err))
            return False
        
        return True
    
    def close(self):
        """
        Close connection to HS.
        """
        
        if self.cnx :
            self.cnx.close()
            self.cnx = None
        
    def get_att_conf(self, attr):
        """
        Get information about an attribute from HS. Required to take the archive.

        Parameters
        ----------
        attr: str
            attribute name
        Returns
        -------
        arr
            Array with information about the device with HS. Fields from att_conf table
        None
            in case of error
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
        
    def replace_att_conf(self, data_type, attr):
        """
        Add attribute to HS. Required for archiving. Adds to hdbpp.att_conf
        
        Parameters
        ----------
        data_type: str
            string attribute type (for example: scalar_devboolean_ro)
        attr: str
            attribute name
            
        Returns
        -------
        arr
            Array with information about the device with HS. Fields from att_conf table
        None
            in case of error
        """
        
        attr = self.attr_set_server(attr)
        
        cursor = self.cnx.cursor()
        
        attrs = attr.split('/')
        
        try :
            sql = "REPLACE INTO att_conf(att_conf_data_type_id, att_name, facility, domain, family, member, name) " \
            "VALUES({0}, '{1}', '{2}', '{3}', '{4}', '{5}', '{6}') ".format(data_type, attr, self.server_default, attrs[3], attrs[4], attrs[5], attrs[6])
        
            cursor.execute(sql)
                
            self.cnx.commit()
            
            return True
        except mysql.connector.Error as error:
            print("[error]: ", sql)
            return False

    def get_data_type_id(self, data_format, data_type, writable):
        """
        Get numeric data type id by data_format, data_type and writable.
        
        Parameters
        ----------
        data_format: tango._tango.AttrDataFormat
            attribute data format, SCALAR or ARRAY (tango._tango.AttrDataFormat.SCALAR)
        data_type: tango._tango.CmdArgType
            type of given (tango._tango.CmdArgType.DevString)
        writable: tango._tango.AttrWriteType
            access type (tango._tango.AttrWriteType.READ, WRITE, READ_WRITE, READ_WITH_WRITE)
            
        Returns
        -------
        int
            id of the attribute data type, for example 1 for scalar_devboolean_ro
        0
            in case of error
        """
        
        dt = ""
        if (data_format == tango._tango.AttrDataFormat.SCALAR) :
            dt += "scalar_"
        elif (data_format == tango._tango.AttrDataFormat.ARRAY) :
            dt += "array_"
            
        dt += "%"
        
        if (writable == tango._tango.AttrWriteType.READ) :
            dt += "_ro"
        else :
            dt += "_rw"
        
        cursor = self.cnx.cursor()
        
        sql = "SELECT att_conf_data_type_id FROM att_conf_data_type WHERE data_type LIKE '{0}' and tango_data_type = {1}".format(dt, data_type)
        #print(sql)
        cursor.execute(sql)

        result = cursor.fetchall()
        
        if len(result) == 0 :
            return 0
        else :
            return result[0]

    def get_data_type(self, att_conf_data_type_id):
        """
        Get the string data type of an attribute, by the numeric data type identifier.

        Parameters
        ----------
        att_conf_data_type_id: int
            attribute data type
        Returns
        -------
        str
            the string data type of the attribute, such as scalar_devushort_ro
        None
            in case of error
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
        Get the history of saving an attribute.
        Note:
            With default parameters takes history for all time

        Parameters
        ----------
        attr: str
            attribute name
        date_from: datetime
            date from which to take history
        date_to: datetime
            date by which to take history
        Returns
        -------
        array
            values archive
        None
            in case of error
        """
        
        attr = self.attr_set_server(attr)
        
        att_conf_id = 0
        att_conf_data_type_id = 0
        table = ''
        
        # If (date_from && date_to) == None, then we take data for all time
        # Time until which we take data
        if date_to == None :
            # Default up to current time
            date_to = datetime.datetime.now()
        
        # Time from which we take data
        if date_from == None :
            # По умолчанию все данные
            date_from = datetime.datetime(1, 1, 1, 0, 0, 0) 
            
        result = self.get_att_conf(attr)
        if result :
            att_conf_id = result[0]
            att_conf_data_type_id = result[2]
        else:
            return None
        
        # Get the data type, use it to find out in which table the history is stored.
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
    
    def archiving_add(self, dp, attrs):
        """
        Add attributes to the AS. It must be done if it is not.

        Parameters
        ----------
        attrs: array(str)
            array of attribute names

        Returns
        -------
        bool
            True if successful, otherwise False
        """
        
        for i, a in enumerate(attrs):
            ac = dp.get_attribute_config(attrs[i].split("/")[3])
            dti = self.get_data_type_id(ac.data_format, ac.data_type, ac.writable)
            if dti == 0 :
                print("[error]: get_data_type_id({0}, {1}, {2})".format(ac.data_format, ac.data_type, ac.writable))
                return False
            
            attrs[i] = self.attr_set_server(attrs[i])
            
            self.replace_att_conf(dti[0], attrs[i])
        
        argIn = DeviceData()
        argIn.insert(tango._tango.CmdArgType.DevVarStringArray, attrs)
        try:
            self.archive_server.command_inout("AttributeAdd", argIn)
            return True
        except tango.DevFailed as df:
            print("[error]: ", df)
            return False
    
    def archiving_pause(self, attr):
        """
        Pause attribute archiving.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if successful, otherwise False
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
        Remove attribute from AS.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if successful, otherwise False
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
        Start archiving the attribute.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if successful, otherwise False
        """
        
        # If a short attribute name was passed, then convert it to full
        # 'tango://tangobox:10000/ECG/ecg/1/Lead'
        attr = self.attr_set_server(attr)

        # Convert the full name to short
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
        The archiving status of the attribute.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if successful, otherwise False
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
        Stop archiving the attribute.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if successful, otherwise False
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
        Set the archiving strategy for the attribute.

        Parameters
        ----------
        attr: str
            attribute name
        strategy: str
            always ALWAYS, no other strategies

        Returns
        -------
        bool
            True if successful, otherwise False
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
        Set the number of days to archive the attribute.

        Parameters
        ----------
        attr: str
            attribute name
        ttl: int/str
            number of days

        Returns
        -------
        bool
           True if successful, otherwise False
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
        Get the archiving strategy for an attribute.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if successful, otherwise False
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
        Get the number of days the attribute was archived.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        int
            days of archiving
        bool
            False on error
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
        Find out if the attribute is being archived.

        Parameters
        ----------
        attr: str
            attribute name

        Returns
        -------
        bool
            True if yes, False otherwise
        """
        
        ret = self.archiving_status(attr)
        
        if ret["Archiving"] == "Started":
            return True
        
        return False
    
    def attr_set_period(self, attr, period = 0, archive_period = None, archive_abs_change = None, archive_rel_change = None):
        """
        Setting the parameters for archiving the attribute.

        Parameters
        ----------
        attr: str
            attribute name
        period: int
            milliseconds
        archive_period: str
            milliseconds if attribute change threshold is exceeded
        archive_abs_change: str
            attribute change threshold in units
        archive_rel_change: str
            attribute change threshold in percent
        """

        
        ap = AttributeProxy(attr)
            
        if (period > 0) :
            ap.poll(period)                
        else :
            if (ap.is_polled()) :
                ap.stop_poll(attr)
            
        attr_conf = ap.get_config()
                
        attr_conf.events.arch_event.archive_period = str(archive_period)
        attr_conf.events.arch_event.archive_abs_change = str(archive_abs_change)
        attr_conf.events.arch_event.archive_rel_change = str(archive_rel_change)
        
        attr_conf.events.ch_event.abs_change = str(archive_abs_change)
        attr_conf.events.ch_event.rel_change = str(archive_rel_change)
            
        ap.set_config(attr_conf)
        
    def attr_get_period(self, attr):
        """
        Retrieving archive parameters for an attribute.

        Parameters
        ----------
        attr: str
            attribute name
        Returns
        -------
        dict
            Archiving options
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
