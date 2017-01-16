#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import os
import pwd
import MySQLdb as mdb
import sys
import re
from dynamic_creater_global_variables import * 

class database:
    """Used to easily access database values in a dictionary format"""

    def __init__(self):
	self.connect()

    def connect(self):
	self.connection = mdb.connect(host, username, password, specific_database)
	self.connection.autocommit(False)
	self.cursor = self.connection.cursor(mdb.cursors.DictCursor)

    def close(self):
	if self.connection:
	    del self.cursor
	    self.connection.close()

    #get one dict from the database with the given query - meant for most devices
    def get_query_row(self, query):
	try:
	    self.cursor.execute(query)
	    row = self.cursor.fetchone()
	    return row
	except mdb.Error, e:
	    print "Error %d: %s\n" %(e.args[0], e.args[1])
	    return {}	

    #get the list of all dicts that match the given query - meant for devices with multiple rows of software
    def get_query_dict(self, query):
	try:
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            return rows
        except mdb.Error, e:
            print "Error %d: %s\n" %(e.args[0], e.args[1])
	    return {}

class file_generator(object):
    """Holds all of the files in one object, can write them all to a directory"""

    def __init__(self, directory_name = ""):
        self.tb = None
        self.dev = None
        self.cfg_list = []
	self.vman_file = None
	self.directory_name = directory_name

    def set_tb_file(self, tb):
	self.tb = tb

    def set_dev_file(self, dev):
	self.dev = dev

    def set_cfg_files(self, cfg):
	self.cfg_list.append(cfg)
    
    #write testbed file may be in a directory or to its path	
    def write_tb_file(self):
	if(self.directory_name != ""):
	    self.tb.write_to_file(self.directory_name)
	    print "TB File exists in: \""+self.tb.main_file.name+"\"\n"
	else:
	    self.tb.write_to_file()
	    print "TB File exists in: \""+self.tb.main_file.name+"\"\n"

    #write device file may be in a directory or to its path
    def write_dev_file(self):
	if(self.directory_name != ""):
	    self.dev.write_to_file(self.directory_name)
	    print "DEV File exists in: \""+self.dev.main_file.name+"\"\n"
        else:
            self.dev.write_to_file()
	    print "DEV File exists in: \""+self.dev.main_file.name+"\"\n"

    #write configuration files may be in a directory or to its path
    def write_cfg_files(self):
	if(self.directory_name != ""):
            for index in range(0, len(self.cfg_list)):
                self.cfg_list[index].write_to_file(self.directory_name)
		print "CFG File #"+str(index + 1)+" exists in: \""+self.cfg_list[index].main_file.name+"\"\n"
        else:
            for index in range(0, len(self.cfg_list)):
                self.cfg_list[index].write_to_file()
		print "CFG File #"+str(index + 1)+" exists in: \""+self.cfg_list[index].main_file.name+"\"\n"
    
    #write vman file only to a directory
    def set_vman_file(self):
        if self.directory_name != "" and self.dev != None:
            self.vman_file = open(os.path.join(self.directory_name,(self.dev.testbed_name+".vman")), "w+")
            print "Vman File exists in: \""+self.vman_file.name+"\"\n"
            self.write_vman_file()

    def write_vman_file(self):
	vman_keys = self.dev.all_vmans.keys()
	vman_keys.sort()
	for key in vman_keys:
	    self.vman_file.write(key + "   " + self.dev.all_vmans[key])
	    self.vman_file.write("\n")
	self.vman_file.close()

class tb(object):
    """Acts as the tb file for a testbed, will write the tb file"""

    def __init__(self, path, device_list, dev_filename):
	self.path = path
	self.filename = ""
	self.device_list = device_list
	self.main_file = None
	self.dev_name = dev_filename

    #writes all the devices in the tb file format (includes extra devices)
    def write_all_devices(self):
	#group everything until reach ".dev"
	tb_name = re.match(r"^.*?(?=.dev)", self.dev_name).group()
	self.main_file.write("array set ::_TESTBEDS::"+tb_name+" {\n")
	self.main_file.write("    devices\t{")
	for device in self.device_list:
	    self.main_file.write("\n\t"+device.device_name)
	self.main_file.write("\n    }\n")	
    
    #writes include portion writesdev file's name when needed
    def write_includes(self):
	self.main_file.write("    includes\t{\n")
	self.main_file.write("\tdev/auto/"+self.dev_name+"\n")
	self.main_file.write("\tdev/auto/infra.dev\n")
	self.main_file.write("    }\n")

    #writes extra portion
    def write_extra(self):
	self.main_file.write("    extras\t{\n")
	self.main_file.write("\tenableAutoCertProv\n")
	self.main_file.write("    }\n}")

    #since created first can make a directory if user requests a directory but it does not exist, otherwise writes tb file
    def write_to_file(self, directory_path = ""):
	if directory_path != "" and os.path.exists(directory_path):
            self.main_file = open(os.path.join(directory_path, self.filename), "w+")
	elif directory_path != "":
	    os.makedirs(directory_path)
	    self.main_file = open(os.path.join(directory_path, self.filename), "w+")
        else:
            self.main_file = open(self.path, "w+")
	self.write_all_devices()
	self.write_includes()
	self.write_extra()
	self.main_file.close()

class cfg_file:
    """Acts as the cfg file for whichever controller, will write the cfg file"""
    offset_vlan = 0 
    offset_vrrp = 0
    offset_local_pool = 170 

    def __init__(self, path, copy_path, device, dev_file):
	self.path = path
	self.filename = ""
	self.copy_path = copy_path
	self.uplink = ""
	self.main_file = None
	self.device = device
	#need to access a few database functions
	self.dev = dev_file
	self.vlan_usage = []
	self.port_list = []

    #get the vlan IP dict for whatever vlan number
    def get_vlan_ip_dict(self, vlan_num):
        ip_dict = self.dev.database.get_query_row("select * from testvlan where vlan = " + str(vlan_num))
        if ip_dict != {}:
            return ip_dict
        return {}

    #get the vrrp IP dict 
    def get_vrrp_ip_dict(self):
	ip_dict = self.dev.database.get_query_row("select * from testbedipaddress where rolename = \"vrrp\"")
	if ip_dict != {}:
	    return ip_dict	
	return {}
	
    #return the IP for the vlanNum that is unique
    def get_vlan_ip(self, offset, vlan_num):
	ip_dict = self.get_vlan_ip_dict(vlan_num)
	try:
            start_ip = ip_dict["startIp"]
            end_ip = ip_dict["endIp"]
	    #make sure new octet is less than the end octet
            if start_ip != "" and start_ip != None and start_ip != "NULL":
                index_end_s = start_ip.rfind(".")
                index_end_e = end_ip.rfind(".")

                fourth_octet_s = int(start_ip[index_end_s + 1:])
                fourth_octet_e = int(end_ip[index_end_e + 1:])
                new_octet = fourth_octet_s + (offset * 5)

                if new_octet <= fourth_octet_e:
                    new_ip = start_ip[:index_end_s + 1] + str(new_octet)
                    return new_ip
	    
        except KeyError:
            pass

    #return the v6 IP for the vlanNum that is unique
    def get_vlanv6_ip(self, offset, vlan_num):
	ip_dict = self.get_vlan_ip_dict(vlan_num)
        try:
            start_ip = ip_dict["startIpv6"]
            end_ip = ip_dict["endIpv6"]
	    #make sure new octet is less than the end octet
            if start_ip != "" and start_ip != None and start_ip != "NULL":
                index_end_s = start_ip.rfind(":")
                index_end_e = end_ip.rfind(":")

                fourth_octet_s = int(start_ip[index_end_s + 1:])
                fourth_octet_e = int(end_ip[index_end_e + 1:])
                new_octet = fourth_octet_s + (offset * 5)

                if new_octet <= fourth_octet_e:
                    new_ip = start_ip[:index_end_s + 1] + str(new_octet)
                    return new_ip
        except KeyError:
            pass

    #return the vrrp IP for the master/standby accordingly
    def get_vrrp_ip(self, offset):
	ip_dict = self.get_vrrp_ip_dict()
	try:
	    start_ip = ip_dict["startIp"]
            end_ip = ip_dict["endIp"]

            #make sure new octet is less than the end octet
            index_end_s = start_ip.rfind(".")
            index_end_e = end_ip.rfind(".")

            fourth_octet_s = int(start_ip[index_end_s + 1:])
            fourth_octet_e = int(end_ip[index_end_e + 1:])
            new_octet = fourth_octet_s + (offset)

            if new_octet <= fourth_octet_e:
                new_ip = start_ip[:index_end_s + 1] + str(new_octet)
                return new_ip
        except KeyError:
            pass

    #write each vlan that is determined by the database
    def write_vlan(self):
	vlan_list = self.dev.database.get_query_dict("select * from testvlan")
	for vlan_dict in vlan_list:
	    self.main_file.write("vlan " + str(vlan_dict["vlan"]) + "\n")
	    self.vlan_usage.append(vlan_dict["vlan"])
	self.vlan_usage.sort()
	self.main_file.write("\n")

    #write uplink port in the file
    def write_uplink(self):
	if self.uplink != "":
	    #group everything until hit "<" from the beginning
	    uplink = re.search(r"^.*?(?=[<])", self.uplink).group()
	    description = self.dev.device_port_connection(self.device, self.uplink).replace("_", "/")
	    self.main_file.write("interface " + uplink + "\n")
	    self.main_file.write("\tdescription \"GE "+ description +"\"\n")
            self.main_file.write("\ttrusted\n")
            self.main_file.write("\ttrusted vlan 1-4094\n")
            self.main_file.write("\tswitchport mode trunk\n!\n\n")

    #write each port being used along with the second vlan being accessed
    def write_vlan_access(self):
        for port in self.port_list:
	    #group everything until hit "<" from the beginning
	    port = re.search(r"^.*?(?=[<])", port).group()
            self.main_file.write("interface " + port + "\n")
            self.main_file.write("\ttrusted\n")
            self.main_file.write("\ttrusted vlan 1-4094\n")
            self.main_file.write("\tswitchport access vlan " +str(self.vlan_usage[1])+ "\n!\n\n")
	
    #write the vlan interface with all IPs and etc.
    def write_vlan_interface(self):
	for vlan_num in self.vlan_usage:
	    self.main_file.write("interface vlan " + str(vlan_num) + "\n")
            self.main_file.write("\tip address " + self.get_vlan_ip(cfg_file.offset_vlan, vlan_num) + " 255.255.255.0\n")
            self.main_file.write("\tipv6 address " + self.get_vlanv6_ip(cfg_file.offset_vlan, vlan_num) + "/64\n")
	    self.main_file.write("\toperstate up\n")
	    self.main_file.write("\tdescription \"connected\"")
            self.main_file.write("\n!\n\n")
	cfg_file.offset_vlan += 1

    #write the master-redundancy portion for the master<=>standby relationship
    def write_vrrp(self):
	#if one the two variables are not empty 
	if self.device.standby != None or self.device.main != None:
	    ip_address, priority = "", ""
	    vrrp_ip = self.get_vrrp_ip(cfg_file.offset_vrrp)
	    #group all numbers from the end
	    vrrp_num = re.search(r"[\d]+$", vrrp_ip).group()

	    #master
	    if self.device.standby != None:
		ip_address = self.device.standby.admin_ip
		priority = "110"
	    #standby
	    elif self.device.main != None:
		ip_address = self.device.main.admin_ip
		priority = "100"

	    self.main_file.write("\nmaster-redundacy\n")
	    self.main_file.write("master-vrrp "+vrrp_num +"\n")
	    self.main_file.write("peer-ip-address "+ip_address+" ipsec itsabug\n")
	    self.main_file.write("!\n")
            self.main_file.write("vrrp "+vrrp_num+"\n")
            self.main_file.write("  priority " +priority+"\n")
	    self.main_file.write("  ip address "+ vrrp_ip + "\n")
	    self.main_file.write("  vlan 1\n")
	    self.main_file.write("  preempt delay 0\n")
            self.main_file.write("  no shutdown\n")
            self.main_file.write("!\n")
	    self.main_file.write("write mem\n")
	    cfg_file.offset_vrrp += 1

	#write mem at the end of a master cfg if redundacy not present    
	else:
	    self.main_file.write("\nwrite mem\n")

    #changes the hostname
    def change_hostname(self, line):
        if line.startswith("hostname"):
	    self.main_file.write("hostname \""+self.device.device_name+"\"\n")
	    return True
	return False

    #changes the master IP
    def change_master_ip(self, line):
	if line.startswith("masterip") and type(self.device.main) is str:
	    self.main_file.write("masterip " + self.device.main + " ipsec itsabug\n")
	    return True
	return False

    #changes the 12tppool1 IP
    def change_local_pool(self, line):
	if line.startswith("ip local pool") and cfg_file.offset_local_pool <= 254:
	    self.main_file.write("ip local pool 12tppool1 173.36."+str(cfg_file.offset_local_pool)+".1 173.36."+str(cfg_file.offset_local_pool)+".254\n")
	    cfg_file.offset_local_pool += 1
	    return True
	return False

    #writes the file based on the base file of whichever controller currently writing for (master or local)
    def write_to_file(self, directory_path = ""):
	if directory_path != "" and os.path.exists(directory_path):
            self.main_file = open(os.path.join(directory_path, self.filename), "w+")
        else:
            self.main_file = open(self.path, "w+")
	with open(self.copy_path, "r") as f:
	    for line in f:
		#the first buffer when the line is only an end-of-line character
		if line.startswith("\n"):
		    self.write_vlan()
		    self.write_uplink()
		    self.write_vlan_access() 
		    self.write_vlan_interface()
		elif self.change_hostname(line):
		    continue
		elif self.change_master_ip(line):
		    continue
		elif self.change_local_pool(line):
		    continue
		else:
		    self.main_file.write(line)
	    #only applies to master controllers
	    if self.device.rolename == "master":
	        self.write_vrrp()
	self.main_file.close()

    def reset_offsets(self):
	cfg_file.offset_vlan = 0
	cfg_file.offset_vrrp = 0
	cfg_file.offset_local_pool = 170
 		
class dev_file(object):
    """Creates all the files necessary for the testbed, will write the files"""

    def __init__(self, json_dict = {}):
        self.device_list = []
	self.extra_list = []
	self.path = ""
	self.filename = ""
	self.main_file = None
	self.json_dict = json_dict
	self.testbed_name = ""
	self.num_of_masters = 0
	self.num_of_locals = 0
	self.database = database()
	self.all_vmans = {}

    def add_device(self, device):
        self.device_list.append(device)

    def find_device(self, device_info):
	for device in self.device_list:
	    if re.search(device_info, device.device_name, re.I):
		return device
	    elif re.search(device_info, device.device_role, re.I):
		return device
	    elif re.search(device_info, device.device_type, re.I):
		return device
	    elif re.search(device_info, device.rolename, re.I):
		return device
	return False

    def set_testbed_name(self, testbed_name):
	self.testbed_name = testbed_name

    def set_dev_path(self, dev_path):
	self.path = dev_path

    #Makes sure that the master controller is written first
    def move_master_to_top(self):
	for index in range(0, len(self.device_list)):
	    if self.device_list[index].if_master() and self.device_list[index] != self.find_device(r"backup|standby"):
		master = self.device_list[index]
		self.device_list.remove(master)
		self.device_list.insert(0, master)
		break

    #Makes sure that the local controllers and then standby is written in order
    def move_local_to_top(self):
	top = 0
	for index in range(0, len(self.device_list)):
	    if self.device_list[index].if_local():
		local = self.device_list[index]
		self.device_list.remove(local)	
		self.device_list.insert(top, local)
		top += 1
	standby = self.find_device(r"backup")
	if standby and standby.if_master():
	    for index2 in range(0, len(self.device_list)):
		if self.device_list[index2] == standby:
		    standby = self.device_list[index2]
		    self.device_list.remove(standby)
		    self.device_list.insert(top, standby)
		    break

    def move_xconnect_to_top(self):
	for index in range(0, len(self.device_list)):
	    if self.device_list[index].rolename == "insideXconnect1":
		inside = self.device_list[index]
		self.device_list.remove(inside)
		self.device_list.insert(0, inside)

        for index in range(0, len(self.device_list)):
	    if self.device_list[index].rolename == "outsideXconnect1":
		outside = self.device_list[index]
                self.device_list.remove(outside)
                self.device_list.insert(0, outside)

    def if_used(self, device, usage_list):
	for used_device in usage_list:
	    if device.device_name == used_device.device_name:
		return True
	return False

    #Make sure APs are ordered in terms of all of the devices order and then LMS number 
    def sort_aps(self):
	top = 0
	sorted_devices = []
        for device in self.device_list:
	    if not(device.if_ap()) and device.lms_dict != {} and not(self.if_used(device, sorted_devices)):
		lms_list = device.lms_dict.keys()
		lms_list.sort()
		for lms in lms_list:
		    for index in range(top, len(self.device_list)):
			if self.device_list[index].device_name == device.lms_dict[lms]:
			    ap = self.device_list[index]
			    self.device_list.remove(ap)
			    self.device_list.insert(top, ap)
			    top += 1
			    break
		sorted_devices.append(device)

    def set_standby(self):
	for device in self.device_list:
	    try:
		standby = device.full_dict[device.device_name]["EXTRA"][0]["STANDBY_LIST"]
		standby_device = self.find_device(standby)
		if standby_device:
		    device.standby = standby_device
		    standby_device.main = device
	    except KeyError:
	        pass

    def set_local(self):
	for device in self.device_list:
	    if len(device.local_list) > 0:
		self.set_master_ip(device, device.local_list)
	
    def set_master_ip(self, device, local_list):
	for local in local_list:
	    local_device = self.find_device(local)
	    if local_device:
		local_device.main = device.admin_ip	
	
    def set_main_dynamic_dict(self, device):
	if device.main_dynamic_type != "":
	    if device.main_id != -1:
	        device.main_dynamic_dict = self.database.get_query_row("select * from "+device.main_dynamic_type+" where id = "+str(device.main_id))
	else:
	    device.main_dynamic_dict = None

    def set_interface_dynamic_dict(self, device, main_id = -1, card_id = "", port_id = ""):
	if device.interface_dynamic_type != "":
	    #for setting VERI
	    if card_id != "" and port_id != "" and device.main_id != -1:
                device.interface_dynamic_dict = self.database.get_query_row("select * from " + device.interface_dynamic_type + " where veriwave_id = " + str(device.main_id) + " and card_id = " + card_id + " and port_id = " + port_id)
            #for setting IXIA
	    elif main_id != -1:
                device.interface_dynamic_dict = self.database.get_query_row("select * from " + device.interface_dynamic_type + " where id = " + str(main_id))
	    #for setting everything else
	    else:
                device.interface_dynamic_dict = self.database.get_query_row("select * from " + device.interface_dynamic_type + " where id = " + str(device.main_id))
	else:
	    device.interface_dynamic_dict = None

    def set_software_dynamic_dict(self, device):
	if device.software_dynamic_type != "":
	    if device.software_dynamic_type == "cage_clients_softwares":
                device.software_dynamic_dict = self.database.get_query_dict("select * from " + device.software_dynamic_type + " where cage_client_id = " + str(device.cage_id))
            elif device.software_dynamic_type == "wired_clients_softwares":
                device.software_dynamic_dict = self.database.get_query_dict("select * from " + device.software_dynamic_type + " where name = \"" + str(device.actual_name) +"\"")
            elif device.main_id != -1:
	        device.software_dynamic_dict = self.database.get_query_row("select * from " + device.software_dynamic_type + " where id = " + str(device.main_id))	
	else:
	    device.software_dynamic_dict = None

    def set_testbed_ip_address(self, device):
	ip_dict = self.database.get_query_row("select * from testbedipaddress where rolename = \"" + device.rolename +"\"")
	if ip_dict != None:
	    return ip_dict
	return {} 

    def create_cfg_files(self, device):
        if device.rolename == "master":
            self.num_of_masters += 1
            filename = self.testbed_name+"-"+device.rolename+str(self.num_of_masters)+".cfg"
	    #if the device is a standby
	    if device.main != None:
		filename = self.testbed_name+"-"+device.rolename +str(self.num_of_masters)+"_standby"+".cfg"
            self.main_file.write("    CONFIG\t\t" + "cfg/"+filename+"\n")
            path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/" + filename
	    #path = cfg_path + filename
            device.cfg = cfg_file(path, master_copy_path, device, self)
	    device.cfg.filename = filename

        elif device.rolename == "local":
            self.num_of_locals += 1
            filename = self.testbed_name+"-"+device.rolename+str(self.num_of_locals)+".cfg"
            self.main_file.write("    CONFIG\t\t" + "cfg/"+filename+"\n")
            path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/" + filename
            #path = cfg_path + filename
            device.cfg = cfg_file(path, local_copy_path, device, self)
	    device.cfg.filename = filename


    def write_ip_information(self, device):
	if device.main_dynamic_dict != None:
	    power_cycler_ip, console_ip = "", ""
	    ip_dict = device.main_dynamic_dict
     
  	    try:
	        power_cycler_ip = ip_dict["power_cycle"]
	    except KeyError:
	        pass

	    try:
	        console_ip = ip_dict["console"]
	    except KeyError:
	        pass

            if device.admin_ip != "" and device.admin_ip != None and device.admin_ip != "NULL" and device.admin_ip[0].isdigit():
		#in case database entry has end-of-line character
                device.admin_ip = device.admin_ip.replace('\n', '')
		if re.search(r"ata", device.device_type,re.I):
		    self.main_file.write("    ADMIN_IP\t" + device.admin_ip + "\n")
		else:
		    self.main_file.write("    ADMIN_IP\t\t" + device.admin_ip + "\n")

	    self.create_cfg_files(device)

            if power_cycler_ip != "" and power_cycler_ip != None and power_cycler_ip != "NULL" and power_cycler_ip[0].isdigit():
                #in case database entry has end-of-line character
                power_cycler_ip = power_cycler_ip.replace('\n', '')
		self.main_file.write("    POWER_CYCLER\t" + power_cycler_ip + "\n")

	    if console_ip != "" and console_ip != None and console_ip != "NULL" and console_ip[0].isdigit():
                #in case database entry has end-of-line character
                console_ip = console_ip.replace('\n', '')
		self.main_file.write("    CONSOLE_IP\t\t" + console_ip + "\n")

    #To make sure there is a recipient for each connection
    def reciprocal_check(self, device_name, keyword):
        try:
            check = self.json_dict[keyword]["CONNECTIONS"][0][device_name]
	    #if list is empty
	    if len(check) > 0:
                return True
	    return False
        except KeyError:
            return False

    """
    The values here are for the left column of the CONNECT section in the dev file
    Returns the necessary port info from the specific device (device) to another device
    """
    def device_port_connection(self, device, port):
        device_port = ""
	#if has port info, rather than no extra info
	if re.search(r"<=>", port):
            if port.startswith("gigabitethernet"):
		#group the numbers and "/" (0/0/0)
                device_port = re.search(r"[\d/]+", port).group()
                device_port = device_port.replace('/', '_')
            elif port.startswith("wired"):
                device_port = "WIRED"
            elif port[0].isdigit() and device:
		#if a veri device
		if re.search(r"veri", device.device_name, re.I) or re.search(r"veri", device.device_type, re.I):
		    #group everything until hit "<" from the beginning
		    port_id = re.search(r"^.*?(?=[<])", port).group()
		    self.set_interface_dynamic_dict(device, port_id)
		    if device.interface_dynamic_dict != None:
			#device_port = \d_\d (veri example: 3_1)
			device_port = str(device.interface_dynamic_dict["card_id"])+"_"+str(device.interface_dynamic_dict["port_id"]) 
	        else:
		    #ID + group everything until hit "<" from the beginning (ixia)
                    device_port = "ID" + re.search(r"^.*?(?=[<])", port).group()
            else:
		#group everything until hit "<" from the beginning
		device_port = re.search(r"^.*?(?=[<])", port.upper()).group()

	#just make sure letters are capatilized
        else:
	    device_port = port.upper()

	return device_port

    #so numbers like 1, 2, 3, 10, 20, 30 don't sort to 10, 20, 30, 1, 2, 3 (which the built-in sort function does)
    def sort_numerically(self, sort_list):
	single = []
	double = []
	for port in sort_list:
	    #if double digit connection/interface
	    if re.search(r"\/\d\d", port) or re.search(r"^\d_\d_\d\d", port) or re.search(r"LMS\d\d", port):
		double.append(port)
	    else:
		single.append(port)
	single.sort()
	double.sort()
	sort_list = single + double
	return sort_list

    #Make sure port list is ordered correctly
    def sort_list(self, port_list):
	sort_list = []
	for index in range(0, len(port_list)):

	    # for ordering port single/double digit ports or LMS in connect portion
	    if re.search(r"<=>", port_list[index]):
		#sort gigabitethernet port and LMS numbers numerically, everything else normal sort
		if re.search(r"gigabitethernet", port_list[index], re.I):
		    sort_list.append(port_list[index])
		elif re.search(r"LMS", port_list[index], re.I):
		    sort_list.append(port_list[index])
		else:
		    #so "<=>" doesn't affect the sorting
                    port_list[index] = port_list[index].replace("<=>", "  ")

	    #for ordering single/double digit ports in the interface section
	    elif re.search(r"^\d_\d", port_list[index]):
                sort_list.append(port_list[index])

	for index in range(0, len(sort_list)):
	    #remove numerical ports to be added in front of non-numerical ports
	    port_list.remove(sort_list[index])

        sort_list = self.sort_numerically(sort_list)
        port_list.sort()

        for index in range(0, len(port_list)):
            port_list[index] = port_list[index].replace("  ", "<=>")

	port_list = sort_list + port_list
        return port_list

    port_usage = {}

    """
    The values here are for the right column of the CONNECT section in the dev file
    Returns the port info from another device (opposite_device) to the specific device (device)
    """
    def reciprocal_port_connection(self, device, port):
	extra = ""
	opposite_device = self.find_device(device.port_connection_dict[port])
	if opposite_device:
	    reciprocal_keys = opposite_device.port_connection_dict.keys()
	    reciprocal_ports = []
	    #gets all the connections from the opposite device to device
	    for key in reciprocal_keys:
		if opposite_device.port_connection_dict[key] == device.device_name:
		    reciprocal_ports.append(key)

	    if len(reciprocal_ports) > 0:
		reciprocal_ports = self.sort_list(reciprocal_ports)
		for reciprocal_index in range(0, len(reciprocal_ports)):
		    #choose a port
		    port = reciprocal_ports[reciprocal_index]
		    match = False
		    #check if this port was used for the connection between the two device
		    for key in dev_file.port_usage.keys():	
			if key == opposite_device.device_name:
			    for key_index in range(0, len(dev_file.port_usage[key])):
				#if port is already used
				if port == dev_file.port_usage[key][key_index]:
				    match = True
				    break

		    #if port was used select the next port
		    if match:
			continue
		    #if port has not been used and no other device is mentionioned other than "opposite_device" and "device"
		    if device.dont_find_other_device(device.device_name, opposite_device.device_name, port):
			extra = port.lower()
			#add to port to port_usage to list of connections with opposite_device 
			if dev_file.port_usage.has_key(opposite_device.device_name):
			    dev_file.port_usage[opposite_device.device_name].append(port)
			#create a new list of used ports with oppsosite_device
			else:
			    dev_file.port_usage[opposite_device.device_name] = []
			    dev_file.port_usage[opposite_device.device_name].append(port)
			#return port 
			break
	return extra
	
    def write_connect(self, device):
	try:
	    port_connection_list = self.sort_list(device.port_connection_dict.keys())
            duplicates = 0
	    connection = False
	    for port in port_connection_list:
		if self.reciprocal_check(device.device_name, device.port_connection_dict[port]):
		    connection = True
	    if not(connection):
		return
	
	    self.main_file.write("    CONNECT\t\t{\n")
	    for port in port_connection_list:
	    	device_port, keyword_port = "", ""

		device_port = self.device_port_connection(device, port)

	        #Reciprocal device's port ID/Number	
                reciprocal_port = self.reciprocal_port_connection(device, port)
		reciprocal_trim = self.device_port_connection(self.find_device(device.port_connection_dict[port]), reciprocal_port)
		device.reciprocal_connection_dict[device_port] = reciprocal_port
		if reciprocal_trim != "":
		    keyword_port = device.port_connection_dict[port] + "." + reciprocal_trim
		else:
		    keyword_port = device.port_connection_dict[port]
		if device_port != "" and keyword_port != "" and reciprocal_trim != "":
	            self.main_file.write("\t" + device_port + "\t\t" + keyword_port + "\n")
		    if device.interface_dict.has_key(device_port):
                        device.interface_dict[device_port + "@" + str(duplicates)] = port
                        duplicates += 1
                    else:
                        device.interface_dict[device_port] = port
	        device.vman_dict[port] = reciprocal_port
	    dev_file.port_usage = {}
            self.write_connect_lms(device)
	    self.main_file.write("    }\n")
	except KeyError:
	    pass

    def write_connect_lms(self, device):
	lms_numbers = device.lms_dict.keys()
        lms_numbers = self.sort_list(lms_numbers)
        for number in lms_numbers:
            device_port, keyword_port = "", ""
            if device.if_ap():
                device_port = "LMS"
                keyword_port = device.lms_dict[number] + "." + number
            else:
                device_port = number
                keyword_port = device.lms_dict[number] + ".LMS"

            self.main_file.write("\t" + device_port + "\t\t" + keyword_port + "\n")


    def find_ports(self, port1, port2):
	port1_portion, port2_portion = "", ""
	#group a number, :, and multiple/one number after "<=>"
	port1_match = re.search(r"(?<=\<\=\>)[\d]+[:][\d]+",port1)
	if port1_match:
	    port1_portion = port1_match.group()
	#group a number, :, and multiple/one number after "<=>"
	port2_match = re.search(r"(?<=\<\=\>)[\d]+[:][\d]+",port2)
	if port2_match:
	    port2_portion = port2_match.group()

	ports =  port1_portion + "," + port2_portion 
	if port1_portion == "" or port2_portion == "":
	    return False
	else:
	    return ports

    #Writes all Possible Vmans
    def write_vman(self, device):
	if device.if_master() or device.if_local():
	    vman_list = device.vman_dict.keys()
	    vman_list.sort()
	    for vman in vman_list:
	        if self.find_ports(vman, device.vman_dict[vman]):
		    ports = self.find_ports(vman, device.vman_dict[vman])
	            opposite_device = None
	            for check_device in self.device_list:
		        if check_device.device_name == device.port_connection_dict[vman]:
		            opposite_device = check_device	
		    if opposite_device != None:
	 	        vman_name = self.testbed_name + "_" + device.device_name + "_" + opposite_device.device_name       
		        if opposite_device.if_client():
		            self.main_file.write("    INTERFACE."+opposite_device.if_client()+".VMAN.NAME {" + vman_name + "}\n")
                            self.main_file.write("    INTERFACE."+opposite_device.if_client()+".VMAN.PORTS {" + ports + "}\n")

		        elif device.vman_dict[vman].startswith("gigabitethernet"): 
		            self.main_file.write("    INTERFACE.UPLINK.VMAN.NAME {" + vman_name + "}\n")
                            self.main_file.write("    INTERFACE.UPLINK.VMAN.PORTS {" + ports + "}\n")

		        else: 
		            self.main_file.write("    INTERFACE."+opposite_device.device_name+".VMAN.NAME {" + vman_name + "}\n")
                            self.main_file.write("    INTERFACE."+opposite_device.device_name+".VMAN.PORTS {" + ports + "}\n")
			self.all_vmans[vman_name] = ports
	
    def write_static_inferface(self, port, interface):
	port_name, port_type = "", ""
	#group everything until reach [<]
	match = re.search(r"^.*?(?=[<])", port)
        if match:
            port_name = match.group()
	#group letters, spaces, "/", and "_" from the end
        match = re.search(r"[\w\s/_]+$", port)
        if match:
            port_type = match.group()

        if port.startswith("gigabitethernet"):
	    #in case no space between gigabitethernet and port number (0/0/0)
            if port_name.find(" ") == -1:
                port_name = port_name[:15] + " " + port_name[15:]
            self.main_file.write("    INTERFACE."+interface+".NAME  {" + port_name + "}\n")
            self.main_file.write("    INTERFACE."+interface+".TYPE  " + port_type.upper() + "\n")
        elif port.startswith("eth"):
            self.main_file.write("    INTERFACE."+interface+".NAME  " + port_name + "\n")
            self.main_file.write("    INTERFACE."+interface+".TYPE  " + port_type.upper() + "\n")
        elif port.startswith("wlan"):
            self.main_file.write("    INTERFACE."+interface+".NAME  WIRELESSPORT\n")
            self.main_file.write("    INTERFACE."+interface+".TYPE  WIRELESS\n")
        elif port.startswith("wired"):
	    self.main_file.write("    INTERFACE."+interface+".NAME  Wired\n")
            self.main_file.write("    INTERFACE."+interface+".TYPE  " + port_type.upper() +" \n")

    #Getting ID for IXIA
    def get_id(self, port):
        if port.find("ID") != -1:
	    port = re.search(r"[\d]+$", port).group()
        return port

    #Getting Card ID for VERI
    def get_card_id(self, port):
        if port.find("ID") == -1 and port[0].isdigit():
	    return port[0]
	return port

    #Getting Port ID for VERI
    def get_port_id(self, port):
	if port.find("ID") == -1 and port[2].isdigit():
            return port[2]
	return port

    #if the type is not specified for VERI/IXIA
    def get_reciprocal_type(self, reciprocal_string):
	if re.search(r"gigabitethernet", reciprocal_string, re.I):
            return "ETH_GE"
	elif re.search(r"wlan", reciprocal_string, re.I):
            return "WIRELESS"
        return ""

    #For IXIA and VERI; these devices deal with their respective ids, card ids, and port ids
    def write_dynamic_interface_ports(self, device, interface_list):
	if device.interface_dynamic_type == "ixia_server_cards_ports" or device.interface_dynamic_type == "veriwave_server_cards_ports":
            reciprocal_type_dict = device.reciprocal_connection_dict
	    for interface in interface_list:
	        port_name, port_type = "", ""
	        main_id = self.get_id(interface)
		card_id = self.get_card_id(interface)
		port_id = self.get_port_id(interface)
			
		#IXIA	
		if main_id.isdigit(): 
                    self.set_interface_dynamic_dict(device, main_id)

		#VERI
                elif card_id.isdigit() and port_id.isdigit():
                    self.set_interface_dynamic_dict(device, -1, card_id, port_id)

	        if device.interface_dynamic_dict != None:
                    interface_dict = device.interface_dynamic_dict
                    try:
                        ixia_id = str(interface_dict["ixia_id"])
                        if ixia_id != "" and ixia_id != None and ixia_id != "NULL":
                            #in case database entry has end-of-line character
                            ixia_id = ixia_id.replace('\n', '')
                            port_name = "\"" + ixia_id
                    except KeyError:
                        pass

		    try:
			veri_id = str(interface_dict["veriwave_id"])
			if veri_id != "" and veri_id != None and veri_id != "NULL":
                            #in case database entry has end-of-line character
                            veri_id = veri_id.replace('\n', '')
                            port_name = "\"" + veri_id
		    except KeyError:
			pass
    	        
		    try:
                        card_id = str(interface_dict["card_id"])
                        if card_id != "" and card_id != None and card_id != "NULL":
                            #in case database entry has end-of-line character
                            card_id = card_id.replace('\n', '')
                            port_name = port_name + " " + card_id
                    except KeyError:
                        pass

	            try:
                        port_id = str(interface_dict["port_id"])
                        if port_id != "" and port_id != None and  port_id!= "NULL":
                            #in case database entry has end-of-line character
                            port_id = port_id.replace('\n', '')
                            port_name = port_name + " " + port_id + "\""
		    except KeyError:
                        pass
		port_type = self.get_reciprocal_type(reciprocal_type_dict[interface])
		if port_type == "WIRELESS":
		    port_name = "WIRELESSPORT"
		if port_name != "" and port_type != "":
	            self.main_file.write("    INTERFACE."+interface+".NAME  " + port_name + "\n")
	            self.main_file.write("    INTERFACE."+interface+".TYPE  " + port_type + "\n")

    #Other devices than VERI and IXIA; they have interface tests 
    def write_dynamic_interface_tests(self, device):
	if device.interface_dynamic_type != "ixia_server_cards_ports" and device.interface_dynamic_type != "veriwave_server_cards_ports":
	    self.set_interface_dynamic_dict(device)
	    interface_dict = device.interface_dynamic_dict
	    test_num = 1
	    if interface_dict != None:
		while test_num <= 3:
		    test_name, test_ip, test_mask, test_gw, test_type, test_adapter = "", "", "", "", "", ""
		    try:
                        test_name = interface_dict["test_"+str(test_num)+"_name"]
                        if test_name != "" and test_name != None and test_name != "NULL":
                            #in case database entry has end-of-line character
                            test_name = test_name.replace('\n', '')
                            self.main_file.write("    INTERFACE."+test_name.upper()+".NAME  " + test_name + "\n")
                    except KeyError:
                        pass
		    
		    try:
                        test_ip = interface_dict["test_"+str(test_num)+"_ip"]
                        if test_ip != "" and test_ip != None and test_ip != "NULL":
                            #in case database entry has end-of-line character
                            test_ip = test_ip.replace('\n', '')
                            self.main_file.write("    INTERFACE."+test_name.upper()+".IP  " + test_ip + "\n")
                    except KeyError:
                        pass
	
		    try:
                        test_mask = interface_dict["test_"+str(test_num)+"_mask"]
                        if test_mask != "" and test_mask != None and test_mask != "NULL":
                            #in case database entry has end-of-line character
                            test_mask = test_mask.replace('\n', '')
                            self.main_file.write("    INTERFACE."+test_name.upper()+".MASK  " + test_mask + "\n")
                    except KeyError:
                        pass

		    try:
                        test_gw = interface_dict["test_"+str(test_num)+"_gw"]
                        if test_gw != "" and test_gw != None and test_gw != "NULL":
                            #in case database entry has end-of-line character
                            test_gw = test_gw.replace('\n', '')
                            self.main_file.write("    INTERFACE."+test_name.upper()+".GW  " + test_gw + "\n")
                    except KeyError:
                        pass

                    try:
                        test_type = interface_dict["test_"+str(test_num)+"_type"]
                        if test_type != "" and test_type != None and test_type != "NULL":
                            #in case database entry has end-of-line character
                            test_type = test_type.replace('\n', '')
                            self.main_file.write("    INTERFACE."+test_name.upper()+".TYPE  " + test_type + "\n")
                    except KeyError:
                        pass

                    try:
			test_adapter = interface_dict["test_"+str(test_num)+"_adapter"]
                        if test_adapter != "" and test_adapter != None and test_adapter != "NULL":
                            #in case database entry has end-of-line character
                            test_adapter = test_adapter.replace('\n', '')
                            self.main_file.write("    INTERFACE."+test_name.upper()+".ADAPTER  {" + test_adapter + "}\n")
                    except KeyError:
                        pass

		    test_num += 1


    def write_dynamic_lms_interface(self, device, interface_port_list):
        if device.main_dynamic_dict != None:
            lms_dict = device.main_dynamic_dict
            try:
                rappool_name = lms_dict["interface_rappool_name"]
                if rappool_name != "" and rappool_name != None and rappool_name != "NULL":
                    #in case database entry has end-of-line character
                    rappool_name = rappool_name.replace('\n', '')
                    self.main_file.write("    INTERFACE.RAPPOOL.NAME  " + rappool_name + "\n")
            except KeyError:
		pass
            
	    try:
                rappool_type = lms_dict["interface_rappool_type"]
                if rappool_type != "" and rappool_type != None and rappool_type != "NULL":
                    #in case database entry has end-of-line character
                    rappool_type = rappool_type.replace('\n', '')
                    self.main_file.write("    INTERFACE.RAPPOOL.TYPE  " + rappool_type + "\n")
            except KeyError:
                pass

            try:
                rappool_ip = lms_dict["interface_rappool_ip"]
                if rappool_ip != "" and rappool_ip != None and rappool_ip != "NULL":
		    #in case database entry has end-of-line character
		    rappool_ip = rappool_ip.replace('\n', '')
                    self.main_file.write("    INTERFACE.RAPPOOL.IP    " + rappool_ip + "\n")
            except KeyError:
                pass

	    self.write_static_lms_interface(device)

	    #writes interface for connections like eth
            for interface in interface_port_list:
                interface = remove_duplicates(interface)
                port = device.interface_dict[interface]
                self.write_static_inferface(port, interface)
	    
	    try:
		interface_input_pair = lms_dict["interface_input_value_pair"]
		if interface_input_pair != "" and interface_input_pair != None and interface_input_pair != "NULL":
                    #in case database entry has end-of-line character
                    interface_input_pair = interface_input_pair.replace('\n', '')
		    print_extra_pair(self.main_file, interface_input_pair)
	    except KeyError:
		pass
	    
	    try:
                ap_location = lms_dict["location"]
                if ap_location != "" or ap_location != None:
                    #in case database entry has end-of-line character
                    ap_location = ap_location.replace('\n', '')
                    self.main_file.write("    LOCATION\t" + ap_location + "\n")
            except KeyError:
                pass

	#if no dynamic information for the AP	
 	else:
	    self.write_static_lms_interface(device)

	    #writes interface for connections like gigabitethernet or eth
            for interface in interface_port_list:
                interface = remove_duplicates(interface)
                port = device.interface_dict[interface]
                self.write_static_inferface(port, interface)	

    #writes the LMS interface for all device from the LMS list
    def write_static_lms_interface(self, device):
	lms_numbers = device.lms_dict.keys()
        lms_numbers.sort()
        for number in lms_numbers:
            if device.if_ap():
                self.main_file.write("    INTERFACE.LMS.NAME  LMS\n")
                self.main_file.write("    INTERFACE.LMS.TYPE  LMS\n")
            else:
                self.main_file.write("    INTERFACE."+number+".NAME  " + number +"\n")
                self.main_file.write("    INTERFACE."+number+".TYPE  LMS\n")

    #manages the interface portion for all devices, whether statically or dynamically	
    def write_interface(self, device):
	self.write_vman(device)
	interface_port_list = device.interface_dict.keys()
        interface_port_list = self.sort_list(interface_port_list)
	if device.if_ap():
	    #writes interface portion for all APs
	    self.write_dynamic_lms_interface(device, interface_port_list)
	else:
	    #writes interface portion dynamically for all devices that require it
	    if device.interface_dynamic_type != "":
		self.write_dynamic_interface_ports(device, interface_port_list)
		self.write_dynamic_interface_tests(device)
            else:
		#writes interface for connections like gigabitethernet or eth
		for interface in interface_port_list:
                    interface = remove_duplicates(interface)
                    port = device.interface_dict[interface]
                    self.write_static_inferface(port, interface)
	    self.write_static_lms_interface(device)

    def write_uplink_port(self, device):
	keys = device.port_connection_dict.keys()
	uplink = ""
	for key in keys:
	    key = remove_duplicates(key)
	    opposite_deviceice = self.find_device(device.port_connection_dict[key])
	    if opposite_deviceice and opposite_deviceice.rolename == "outsideXconnect1":
		uplink = key
		break

	if uplink.startswith("gigabitethernet"):
	    device.cfg.uplink = uplink
	    uplink = "GE "+self.device_port_connection(device, uplink).replace("_","/")
            self.main_file.write("    SOFTWARE.UPLINK.PORT  {"+uplink+"}\n")
	    	    
    def add_other_ports(self, device):
	if device.cfg != None:
	    keys = self.sort_list(device.port_connection_dict.keys())
	    for port in keys:
		if port.startswith("gigabitethernet") and port != device.cfg.uplink:
		    device.cfg.port_list.append(port)

    def write_controller_software(self, device):
	if device.software_dynamic_dict != None:
            software_dict = device.software_dynamic_dict
            try:
                #esxi_ip = software_dict["esxi_ip"]
		esxi_ip = software_dict["vm_name"]
                if esxi_ip != "" and esxi_ip != None and esxi_ip != "NULL":
                    #in case database entry has end-of-line character
                    esxi_ip = esxi_ip.replace('\n', '')
                    self.main_file.write("    SOFTWARE.ESXI.IP        \"" + esxi_ip + "\"\n")
            except KeyError:
                pass

	    try:
                esxi_user = software_dict["esxi_user"]
                if esxi_user != "" and esxi_user != None and esxi_user != "NULL":
                    #in case database entry has end-of-line character
                    esxi_user = esxi_user.replace('\n', '')
                    self.main_file.write("    SOFTWARE.ESXI.USER      \"" + esxi_user + "\"\n")
            except KeyError:
                pass
	
	    try:
                esxi_password = software_dict["esxi_password"]
                if esxi_password != "" and esxi_password != None and esxi_password != "NULL":
                    #in case database entry has end-of-line character
                    esxi_password = esxi_password.replace('\n', '')
                    self.main_file.write("    SOFTWARE.ESXI.PASSWORD  \"" + esxi_password + "\"\n")
            except KeyError:
                pass

	    try:
                #vm_name = software_dict["vm_name"]
		vm_name = software_dict["esxi_ip"]
                if vm_name != "" and vm_name != None and vm_name != "NULL":
                    #in case database entry has end-of-line character
                    vm_name = vm_name.replace('\n', '')
                    self.main_file.write("    SOFTWARE.VM.NAME        \"" + vm_name + "\"\n")
            except KeyError:
                pass
	
	    try:
                console_type = software_dict["console_server_type"]
                if console_type != "" and console_type != None and console_type != "NULL":
                    #in case database entry has end-of-line character
                    console_type = console_type.replace('\n', '')
                    self.main_file.write("    SOFTWARE.CONSOLESERVER.NAME  " + console_type + "\n")
                    self.main_file.write("    SOFTWARE.AP.CONSOLESERVER.NAME  " + console_type + "\n")		    
            except KeyError:
                pass

	    self.write_uplink_port(device)
	    self.add_other_ports(device)

	    try:
                power_cycler_type = software_dict["power_cycle_type"]
                if power_cycler_type != "" and power_cycler_type != None and power_cycler_type != "NULL":
                    #in case database entry has end-of-line character
                    power_cycler_type = power_cycler_type.replace('\n', '')
                    self.main_file.write("    SOFTWARE.RPC.NAME  " + power_cycler_type + "\n")
            except KeyError:
                pass

	    try:
		mgmt_vlan = software_dict["MGMT_VLAN"]
		if mgmt_vlan != 0:
		    self.main_file.write("    SOFTWARE.MGMT.VLAN  " + str(mgmt_vlan) + "\n")
	    except KeyError:
		pass

    def write_software(self, device):
        if device.software_dynamic_dict != None:
            software_dict = device.software_dynamic_dict
	    if type(software_dict) is dict:
                try:
                    software_version = software_dict["software_version"]
                    if software_version != "" and software_version != None and software_version != "NULL":
                        #in case database entry has end-of-line character
                        software_version = software_version.replace('\n', '')
                        self.main_file.write("    SOFTWARE.IXOS.VERSION  " + software_version + "\n")
                except KeyError:
                    pass
	    
		try:
                    software_pair = software_dict["software_extra_input_value_pair"]
                    if software_pair != "" and software_pair != None and software_pair != "NULL":
                    	#in case database entry has end-of-line character
                    	software_pair = software_pair.replace('\n', '')
                    	print_extra_pair(self.main_file, software_pair)
	    	except KeyError:
                    pass
	    else:
		print_list = []
		for index in range(0, len(software_dict)):
		    software_name = ""
		    try:
			software = software_dict[index]["software"]
			if software != "" and software != None and software != "NULL":
                            #in case database entry has end-of-line character
                            software = software.replace('\n', '')
			    index_end = software.find(".")
			    if index_end != -1:
			        software_name = software[:index_end].upper()
			    else:
				software_name = software.upper()
                            print_list.append("    SOFTWARE."+software_name+".EXE  " + software)
		    except KeyError:
			pass
	
		    try:
			path = software_dict[index]["path"]
			if path != "" and path != None and path != "NULL" and software_name != "":
			    #in case database entry has end-of-line character
                            path = path.replace('\n', '')
                            print_list.append("    SOFTWARE."+software_name+".PATH  " + path)
		    except KeyError:
			pass

		    try:
                        software_pair = software_dict[index]["software_extra_input_value_pair"]
                        if software_pair != "" and software_pair != None and software_pair != "NULL":
                            #in case database entry has end-of-line character
                            software_pair = software_pair.replace('\n', '')
                            print_list.append(print_extra_pair(self.main_file, software_pair, True))
                    except KeyError:
                        pass
		print_list.sort()
		for index in range(0, len(print_list)):
		    self.main_file.write(print_list[index] + "\n")

    def write_mgmt_vlan(self, device):
	try:
	    if device.main_dynamic_dict != None and device.main_dynamic_dict["MGMT_VLAN"] != 0:
		vlan_dict = device.main_dynamic_dict
		self.main_file.write("\t    vlan " + str(vlan_dict["MGMT_VLAN"]) +"\n")
                self.main_file.write("\t    interface vlan " + str(vlan_dict["MGMT_VLAN"]) + "\n")
                self.main_file.write("\t    ip address " + vlan_dict["MGMT_IP"] +" "+ vlan_dict["MGMT_IP_MASK"] +"\n")
		self.main_file.write("\t    !\n")
	except KeyError:
	    pass

    def write_uplink_vlan(self, device):
	outside_xconnect = self.find_device("outsideXconnect1")
	if outside_xconnect and outside_xconnect.main_dynamic_dict != None:
	    ip_dict = outside_xconnect.main_dynamic_dict
	    self.main_file.write("\t    ip default-gateway "+ ip_dict["MGMT_IP"] +"\n")
	    index_end = ip_dict["MGMT_IP"].find(".")
	    firstOctect = (ip_dict["MGMT_IP"][:index_end] + ".0.0.0")
	    self.main_file.write("\t    ip route "+ firstOctect +" 255.0.0.0 "+ ip_dict["MGMT_IP"] +"\n")

	#if there is an uplink port
	if device.cfg.uplink != "":
            port = re.search(r"^.*?(?=[<])", device.cfg.uplink).group()
	    self.main_file.write("\t    interface "+ port +"\n")
	    self.main_file.write("\t    trusted\n")
            self.main_file.write("\t    no shut\n")
            self.main_file.write("\t    trusted vlan 1-4094\n")
            self.main_file.write("\t    switchport mode trunk\n")
	self.main_file.write("\t    !\n")

    def write_extra(self, device):
	#database vlan
	try:
	    outside_xconnect = self.find_device("outsideXconnect1")
            if outside_xconnect and outside_xconnect.main_dynamic_dict != None:
	        self.main_file.write("\t    interface vlan " + str(outside_xconnect.main_dynamic_dict["vlan"]) + "\n")
                self.main_file.write("\t    "+ device.admin_ip +" 255.255.255.0\n")
                self.main_file.write("\t    no shut\n")
                self.main_file.write("\t    !\n")
	        return
	except KeyError:
	    pass
	
	#generic vlan
	if device.admin_ip != "":
	    self.main_file.write("\t    interface vlan 1\n")
	    self.main_file.write("\t    "+ device.admin_ip +" 255.255.255.0\n")
	    self.main_file.write("\t    no shut\n")
            self.main_file.write("\t    !\n")
	
    def write_mini_cfg(self, device):
	self.main_file.write("\n    MINICFG\t{\n")
	self.main_file.write("\tconfig t\n")
	self.write_mgmt_vlan(device)
	self.write_uplink_vlan(device)
	self.write_extra(device)
	self.main_file.write("    }\n")

    #finds the note mentioned in the database and writes it
    def write_note(self, device):
        if device.main_dynamic_dict != None:
            try:
                note = device.main_dynamic_dict["notes"]
                if note != "" and note != None and note != "NULL":
                    #in case database entry has end-of-line character
                    note = note.replace('\n', '')
                    self.main_file.write("    NOTES\t" + "{"+note+"}\n")
                    return
            except KeyError:
                pass

	#check software if only one row and not multiple rows
        if device.software_dynamic_dict != None and type(device.software_dynamic_dict) is dict:
            try:
                note = device.software_dynamic_dict["notes"]
                if note != "" and note != None and note != "NULL":
                    #in case database entry has end-of-line character
                    note = note.replace('\n', '')
                    self.main_file.write("    NOTES\t" +"{"+note+"}\n")
                    return
            except KeyError:
                pass

    def write_prompt(self, device):
	if device.main_dynamic_dict != None:	
	    try:
	        prompt = device.main_dynamic_dict["prompt"]
                if prompt != "" and prompt != None and prompt != "NULL":
                    #in case database entry has end-of-line character
                    prompt = prompt.replace('\n', '')
                    self.main_file.write("    PROMPT\t" + prompt + "\n")
	            return
	    except KeyError:
	        pass

    def write_username_and_password(self, device):
        if device.main_dynamic_dict != None:
            try:
                username = device.main_dynamic_dict["username"]
                if username != "" and username != None and username != "NULL":
                    #in case database entry has end-of-line character
                    username = username.replace('\n', '')
                    self.main_file.write("    USERNAME\t" + username + "\n")
            except KeyError:
                pass

            try:
                password = device.main_dynamic_dict["password"]
                if password != "" and password != None and password != "NULL":
                    #in case database entry has end-of-line character
                    password = password.replace('\n', '')
                    self.main_file.write("    PASSWORD\t" + password + "\n")
            except KeyError:
                pass

    def write_role(self, device):
	if device.device_role != "":
	    self.main_file.write("    ROLE\t" + device.device_role + "\n")

    def write_type(self, device):
	if device.main_dynamic_dict != None:
	    device_type = ""
	    try:
                device_type = device.main_dynamic_dict["type"]	
	    except KeyError:
		pass
	
	    try:
		device_type = device.main_dynamic_dict["os_type"]
	    except KeyError:
		pass

	    try:
		device_type = device.main_dynamic_dict["device_type"]
	    except KeyError:
		pass
	
	    if device_type != "" and device_type != None and device_type != "NULL":
                #in case database entry has end-of-line character
                device_type = device_type.replace('\n', '')
	    	self.main_file.write("    TYPE\t" + device_type + "\n")

	#if no database value    
	elif device.device_type != "":
	    self.main_file.write("    TYPE\t" + device.device_type + "\n")

    #specific order of info for controllers
    def write_controller(self, device):
	self.write_controller_software(device)
	self.write_mini_cfg(device)
	self.write_note(device)
	self.write_username_and_password(device)
	self.write_role(device)
	self.write_prompt(device)
	self.write_type(device)

    #specific order of info for xconnect
    def write_xconnect(self, device):
        self.write_note(device)
        self.write_software(device)
        self.write_prompt(device)
        self.write_role(device)
        self.write_username_and_password(device)
        self.write_type(device)

    #specific order of infor for clients
    def write_client(self, device):
	self.write_prompt(device)
	self.write_software(device)
	self.write_note(device)

    #general order for accessory devices
    def write_other_device(self, device):
	self.write_note(device)
	self.write_software(device)
        self.write_username_and_password(device)
        self.write_role(device)
        self.write_type(device)

    def write_specific_device(self, device):
	if device.if_local() or device.if_master():
            self.write_controller(device)

        elif self.find_device(r"xconnect"):
	    self.write_xconnect(device)

	elif device.if_client():
	    self.write_client(device)
	    self.write_role(device)
            self.write_type(device)
            self.write_username_and_password(device)

        elif self.find_device(r"apsim"):
            self.write_client(device)
	    self.write_username_and_password(device)
            self.write_role(device)
            self.write_type(device)
        else:
            self.write_other_device(device)
    
    def write_to_file(self, directory_path = ""):
	#open in directory
	if directory_path != "" and os.path.exists(directory_path):
            self.main_file = open(os.path.join(directory_path, self.filename), "w+")
        else:
            self.main_file = open(self.path, "w+")

	#writing each device's info
	for device in self.device_list:
	    self.main_file.write("array set ::_DEVICES::" + device.device_name + " {\n")
	    self.write_ip_information(device)

	    if len(device.connection_list) > 0 or len(device.lms_list) > 0:
	        self.write_connect(device)
	        self.write_interface(device)

	    #software, notes, prompt, username/password, type, etc. 
	    self.write_specific_device(device)
	    self.main_file.write("}\n\n")
	
	self.main_file.close()

    #close connection to database
    def end_operations(self):
        self.database.close()

class device_object(object):
    """Acts as a holder for all of a devices info"""

    offset_master = 0
    offset_local = 0

    def __init__(self, dev_file):

	self.dev = dev_file

	#information from JSON file
	self.full_dict = {}    
        self.device_name = ""
    	self.bank_id = -1
	self.cage_id = -1
    	self.connection_list = []
    	self.lms_list = []
    	self.main_id = -1
    	self.actual_name = ""
    	self.device_type = ""
	self.device_role = ""
	self.local_list = []

	#information to be determined with the JSON file
	self.main = None
	self.standby = None
	self.admin_ip = ""
	self.rolename = ""
	self.cfg = None
	self.port_connection_dict = {}
        self.reciprocal_connection_dict = {}
	self.interface_dict = {}
	self.vman_dict = {}
	self.lms_dict = {}
	self.main_dynamic_dict = {}
	self.interface_dynamic_dict = {}
	self.software_dynamic_dict = {}
	self.main_dynamic_type = ""
	self.interface_dynamic_type = ""
	self.software_dynamic_type = ""

    #Make sure that no third-party device is involved in the two-way connection
    def dont_find_other_device(self, device_name, connection_name, port):
	device_list = list(self.full_dict)
	for device in device_list:
	    #if a device is not one of the two devices there is a connection with, but is found in the port details
	    if not(re.search(device, device_name, re.I)) and not(re.search(device, connection_name, re.I)) and re.search(device, port, re.I):
		port_device = re.search(device, port, re.I)
		if port_device.group() == device:
		    return False
	return True

    #to determine if device is a master controller
    def if_master(self):
        match = re.search(valid_master, self.device_role, re.I)
        if match:
            return True
        return False
    
    #to determine if device is a local controller
    def if_local(self):
	match = re.search(valid_local, self.device_role, re.I)
	if match:
	    return True
	return False

    #to determine if device is a client
    def if_client(self):
        match = re.search(valid_client, self.device_name, re.I)
        if match:
            return match.group()
        match = re.search(valid_client, self.device_type, re.I)
        if match:
            return match.group()
        match = re.search(valid_client, self.actual_name, re.I)
        if match:
            return match.group()
        return False

    #to determine if device is a ap
    def if_ap(self):
        match = re.search(valid_ap, self.device_type, re.I)
        if match:
            return True
        return False

    #to determine outside vs inside xconnect
    def if_outside_xconnect(self):
	outside = False
	for connection in self.connection_list:
	    opposite_device = self.dev.find_device(connection)
	    #if there is a connection to a local or master controller
	    if opposite_device and (opposite_device.if_local() or opposite_device.if_master()):
		outside = True	    
	return outside

    """
    To set up queries more easily by setting the column for each devices depending if for main/interface/software
    main_dynamic_type used for all available ips, notes, username/password, types, etc.
    interface_dynamic_type for all test values, port/card id, etc. (apsim, veri, ixia, clients)
    software_dynamic_type for all software, esxi info, paths, etc. (clients, controllers, apsim, ixia/ver/ata) 
    """
    def determine_dynamic_type(self):
	#controllers
	if self.if_local() or self.if_master():
	    self.main_dynamic_type = "controllers"
            self.software_dynamic_type = "controllers"

	#aps
	elif self.if_ap():
	    self.main_dynamic_type = "cage_aps"

	#switches
	elif re.search(r"xconnect", self.device_role, re.I):
	    self.main_dynamic_type = "xconnect_switches"
	
	#wired clients
	elif self.if_client() and self.cage_id == -1:
	    self.main_dynamic_type = "wired_clients"
            self.interface_dynamic_type = "wired_clients"
            self.software_dynamic_type = "wired_clients_softwares"

	#caged clients
	elif self.if_client() and self.bank_id == -1:
            self.main_dynamic_type = "cage_clients"
            self.interface_dynamic_type = "cage_clients"
            self.software_dynamic_type = "cage_clients_softwares"
	
	#apsimserver
        elif re.search(r"apsim", self.device_type, re.I) or re.search(r"apsim", self.device_name, re.I):
            self.main_dynamic_type = "apsim_servers"
            self.interface_dynamic_type = "apsim_servers"
            self.software_dynamic_type = "apsim_servers"

	#ixia
        elif re.search(r"ixia", self.device_name, re.I) or re.search(r"ixia", self.device_type, re.I):
            self.main_dynamic_type = "ixia_servers"
            self.interface_dynamic_type = "ixia_server_cards_ports"
            self.software_dynamic_type = "ixia_servers"
	    self.set_device_id()

        #veri
        elif re.search(r"veri", self.device_name, re.I) or re.search(r"veri", self.device_type, re.I):
            self.main_dynamic_type = "veriwave_servers"
            self.interface_dynamic_type = "veriwave_server_cards_ports"
            self.software_dynamic_type = "veriwave_servers"
	    self.set_device_id()

	#ata
	elif re.search(r"^ata", self.device_name, re.I) or re.search(r"^ata", self.device_type, re.I):
	    self.main_dynamic_type = "ata_servers"
            self.software_dynamic_type = "ata_servers"
	    #if veri device found at the time of setting ata set main id to veri's main id
	    if self.dev.find_device(r"veri"):
		if self.dev.find_device(r"veri").main_id != -1:
		    self.main_id = self.dev.find_device(r"veri").main_id

    """
    Sets the main id for veri/ixia devices by taking one of the port number in its connections and accessing
    Also sets ata devices id if veriwave id is found
    """
    def set_device_id(self):
	main_id = -1
	ports = self.port_connection_dict.keys()
	for port in ports:
	    port_id = re.search(r"^.*?(?=[<])", port).group() 
	    if port_id.isdigit():
		self.dev.set_interface_dynamic_dict(self, port_id)
		if self.interface_dynamic_dict != None:
		    try:
		        main_id = self.interface_dynamic_dict["ixia_id"]		
		        self.main_id = main_id
		    except KeyError:
		        pass
			
		    try:
			main_id = self.interface_dynamic_dict["veriwave_id"]
			self.main_id = main_id
			#sets ata id to veriwave_id, trumps any previous ids
			ata_device = self.dev.find_device(r"^ata")
                        if main_id != -1 and ata_device:
                            ata_device.main_id = main_id
		    except KeyError:
			pass
		    break
	#if all wlan connections and no port number available to get an id 
	if main_id == -1:
	    self.main_id = self.bank_id
	#if ata does not have any id
	ata_device = self.dev.find_device(r"^ata")
        if ata_device and ata_device.main_id == -1:
            ata_device.main_id = self.bank_id	

    def set_rolename(self):
	if self.if_local():
	    self.rolename = "local"
	elif self.if_master():
	    self.rolename = "master"
	elif re.search(r"xconnect", self.device_role, re.I) and self.if_outside_xconnect():
	    self.rolename = "outsideXconnect1"
	elif re.search(r"xconnect", self.device_role, re.I):
	    self.rolename = "insideXconnect1"

    """
    Sets the admin ip according to whether the device has the key in its main dict
    Or sets up the admin ip based on what role the device is
    """
    #sets Admin IP for devices through database or offsets for controllers/switches	
    def set_admin_ip(self):
        try:
	    #ip from main_dynamic_dict
            if self.rolename == "":
                if self.main_dynamic_dict != None:
                    ip_dict = self.main_dynamic_dict
                    try:
                        self.admin_ip = ip_dict["mgmt_ip"]
                    except KeyError:
                        pass
	    #generate ip from "testbedipaddress" in the database
            else:
                ip_dict = self.dev.set_testbed_ip_address(self)
                try:
                    start_ip = ip_dict["startIp"]
                    end_ip = ip_dict["endIp"]

                    if start_ip != "" and start_ip != None and start_ip != "NULL":
                        if end_ip != "" and end_ip != None and end_ip != "NULL":
			    #group all the numbers after "." from the end (fourth octet)
                            fourth_octet_s = re.search(r"(?<=.)[\d]+$", start_ip).group()
                            fourth_octet_e = re.search(r"(?<=.)[\d]+$", end_ip).group()
                            new_octet = int(fourth_octet_s)

                            if self.rolename == "master":
                                new_octet += (device_object.offset_master * 5)
                                device_object.offset_master += 1

                            elif self.rolename == "local":
                                new_octet += (device_object.offset_local * 5)
                                device_object.offset_local += 1

			    #make sure new octet is less than last possible octet
                            if new_octet <= int(fourth_octet_e):
				new_ip = re.search(r"[\d]+[.][\d]+[.][\d]+[.]", start_ip).group() + str(new_octet)
                                self.admin_ip = new_ip
                        else:
                            self.admin_ip = start_ip
                except KeyError:
                    pass
        except KeyError:
            pass

    """
    Each device's information
    device_name is the name seen in the dev file, device_dict holds the information, full_dict set for later access
    """
    def set_device(self, device_name, device_dict, full_dict):
        
	#hold the entire dictionary for finding other devices    	
	self.full_dict = full_dict

	#sets the device name for "array set ::_DEVICES::"
	self.device_name = device_name
	
	#bank id
        try:
	    self.bank_id = device_dict["BANK_ID"]
	except KeyError:
	    pass

	#cage id
	try:
	    self.cage_id = device_dict["CAGE_ID"]
	except KeyError:
	    pass
 
	#devices that this device has connections with
	try:
	    self.connection_list = list(device_dict["CONNECTIONS"][0])
	    self.connection_list.sort()
	except KeyError:
	    pass

	#devices that this device creates LMS with
	try:
	    self.lms_list= list(device_dict["LMS"][0])
	    self.lms_list.sort()
	except KeyError:
	    pass
	
	#id
	try:
	    self.main_id = device_dict["ID"] 
	except KeyError:
	    pass

	#technical name
	try:
	    self.actual_name = device_dict["NAME"]
	except KeyError:
	    pass
	
	#device type
	try:
	    self.device_type = device_dict["DEVICE_INFO"][0]["TYPE"]
	except KeyError:
	    pass

	#device role
	try:
	    self.device_role = device_dict["DEVICE_INFO"][0]["ROLE"]
	except KeyError:
	    pass
	
	#local list
	try:
	    self.local_list = device_dict["EXTRA"][0]["LOCAL_LIST"]
	    self.local_list.sort()
	except KeyError:
	    pass
	
	#port connections - maps a connection(key) to the receiving device(value)
	try:
	    port_dict = {}
            duplicates = 0
            if len(self.connection_list) > 0:
                for connection in self.connection_list:
		    #if there is a list for the connections between self and connection from list
                    if (type(device_dict["CONNECTIONS"][0][connection]) is list):
                        length = len(device_dict["CONNECTIONS"][0][connection])
			#add all connections to this device
                        for index in range(0, length):
			    port = device_dict["CONNECTIONS"][0][connection][index]
			    #check to see if only the two devices are mentioned
			    if self.dont_find_other_device(device_name, connection, port):
				#add to dict
			        port_dict[port.lower()] = connection
            
	    self.port_connection_dict = port_dict
        except KeyError:
            pass

	#maps LMS(key) to its LMS number(value)
	try:
	    for lms in self.lms_list:
	    	number = device_dict["LMS"][0][lms]
		self.lms_dict[number] = lms

	except KeyError:
	    pass

	#needed to set up the queries to get the database values
	self.determine_dynamic_type()

#removes the set duplicate marker from strings if they exist
def remove_duplicates(duplicate):
    if duplicate.find("@") != -1:
        index_end = duplicate.find("@")
	duplicate = duplicate[:index_end]
	return duplicate
    else:
	return duplicate

"""
Break up and print/return the pieces of the software string
list_bool used to return individual software pieces for a list of multiple dicts on one device
If there is not multiple software, then print software; otherwise return each piece of software to list
"""
def print_extra_pair(new_file, software_pair, list_bool = False):
    if software_pair.find(":") != -1:
        index_end_input = software_pair.find(":")
        index_end_value = software_pair.find("-")

	#if theres more software on the string
        if index_end_value != -1:

	    #if need to return each portion to a list 
	    #more extra input pairs than this one
	    if list_bool:
                next_portion = software_pair[index_end_value + 1:]
		#recursively get the next portion
                print_extra_pair(new_file, next_portion, True)
                return ("    " + software_pair[:index_end_input] + "  " + software_pair[index_end_input + 1: index_end_value])

	    #otherwise just print each part of the one software string
	    else:
		new_file.write("    " + software_pair[:index_end_input] + "  " + software_pair[index_end_input + 1: index_end_value] + "\n")
                next_portion = software_pair[index_end_value + 1:]
		#recursively get next portion
                print_extra_pair(new_file, next_portion)

	#otherwise reached the end of the string
        else:
	    if list_bool:
               return ("    " + software_pair[:index_end_input] + "  " + software_pair[index_end_input + 1:])
	    else:
               new_file.write("    " + software_pair[:index_end_input] + "  " + software_pair[index_end_input + 1:] + "\n")
    else: 
        pass

"""
Requires user input to check when they want to overite an existing file
Returns true or false depending on answers
"""
def overwrite_file():
    answer = False
    response = raw_input("Do you want to overwrite this file, and create the required files? (y/n): ")
    while (response != "y" and response != "Y" and response != "Yes" and response != "yes") and (response != "n" and response != "N" and response != "No" and response != "no"):
        response = raw_input("\nInvalid Input! Do you want to overwrite this file? (y/n): ")

    if response == "y" or response == "Y" or response == "Yes" or response == "yes":
        response2 = raw_input("\nSo...overwrite and create this as a new file? (y/n): ")
        while (response2 != "y" and response2 != "Y" and response2 != "Yes" and response2 != "yes") and (response2 != "n" and response2 != "N" and response2 != "No" and response2 != "no"):
            response2 = raw_input("\nInvalid Input! Do you want to overwrite this file? (y/n): ")

        if response2 == "y" or response2 == "Y" or response2 == "Yes" or response2 == "yes":
            answer = True
        else:
            answer = False
    else:
        answer = False
    return answer

"""
Used to find an available json path to get testbed files info 
set_json_file is used to bypass the selection of a json file
Return true if file path is available, false otherwise
"""
def available_json_file(set_json_file = ""):
    try:
	if set_json_file == "":
            file_name = raw_input("Enter the json file path/name: ")
	    json_portion = file_name[-5:]
            while json_portion != ".json":
                print "\nYour file name does not end in \".json\"!\n"
                file_name = raw_input("Enter json file path/name: ")
                json_portion = file_name[-5:]   
	    path = file_name
            if os.path.isfile(path):    
                return file_name
	    else:
	        print "\nYour file \"" + file_name + "\" does not exist, try again!\n"
	        return False
	else:
	    json_portion = set_json_file[-5:]
            if json_portion != ".json":
                print "\nYour file name does not end in \".json\"!\n"
		return False
	    else:
		if os.path.isfile(set_json_file):
		    return set_json_file
		else:
		    print "\nYour file \"" + set_json_file + "\" does not exist!\n"
		    return False 
    except KeyboardInterrupt:
	print "\n"
	return -1

"""
Used to find an available dev path, checks if user wants to overwrite any copies
Uses dev to set its path for access; set_dev_file is used to bypass the selection of a dev file; directory_path to create a directory if present
Return true if file path is available, false otherwise
"""
def available_dev_file(dev, set_dev_file = "", directory_path = ""):
    try:
	path = ""
	if set_dev_file == "":
            dev_name = raw_input("Enter the dev file name: ")
            while not(dev_name.endswith(".dev")):
                print "\nYour file name does not end in \".dev\"!\n"
                dev_name = raw_input("Enter the dev file name: ")
	    index_end = dev_name.find(".dev")
	    dev.set_testbed_name(dev_name[:index_end])
            #path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/qa/automation/configs/dev/auto/" + dev_name
            path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/" + dev_name
	    dev.filename = dev_name
	else:
	    if set_dev_file.endswith(".dev"):
	        index_end = set_dev_file.find(".dev")
                dev.set_testbed_name(set_dev_file[:index_end])
                #path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/qa/automation/configs/dev/auto/" + set_dev_file
                path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/" + set_dev_file
		dev.filename = set_dev_file	
	    else:
		print "\nYour file name does not end in \".dev\"!"
		return False
        if os.path.isfile(path) and directory_path == "":
            print "\nThis file already exists!:", path, "\n"
	    if overwrite_file():
                dev.set_dev_path(path)
                print "\nYour files have been created!\nCheck and see if your files are complete!\n"
                return True
            else:
                return False

	elif directory_path != "":
	    print "\nDirectory entered:", directory_path, "\n"
	    response = raw_input("Your files will be added to the following directory \""+directory_path+"\", do you want this? (y/n): ")

            while (response != "y" and response != "Y" and response != "Yes" and response != "yes") and (response != "n" and response != "N" and response != "No" and response != "no"):
                response = raw_input("\nInvalid Input! Do you want the files added to the directory? (y/n): ")

            if response == "y" or response == "Y" or response == "Yes" or response == "yes":
                print "\nYour files have been created!\nCheck the directory: \""+ directory_path + "\" and see if your files are complete!\n"
                return True
            else:
                return False

        else:
            print "\nThis file does not exist!:", path, "\n"

            response = raw_input("So...create all the files, including \"" + dev.filename + "\" as a new file? (y/n): ")
	    while (response != "y" and response != "Y" and response != "Yes" and response != "yes") and (response != "n" and response != "N" and response != "No" and response != "no"):
                response = raw_input("\nInvalid Input! Do you want to create new files? (y/n): ")

            if response == "y" or response == "Y" or response == "Yes" or response == "yes":
                dev.set_dev_path(path)
                print "\nYour files have been created!\nCheck and see if the files are complete!\n"
                return True
            else:
                return False
    except KeyboardInterrupt:
	print "\n"
        return -1


"""
Makes sures bank IDs are the same if available
Prints out any errors with the ids, return true if ids are same, false otherwise
Uses testbed to get the list of devices to check ids
"""
def check_bank_id(dev):
    check = -1
    #gets the first valid bank ID
    #uses it as a check for the other devices' bank IDs
    for device in dev.device_list:
        if device.bank_id != -1:
	    check = device.bank_id
	    break

    for device in dev.device_list:
	if not(device.bank_id == -1 or device.bank_id == check):
	    print (device.device_name + "'s"), "Bank ID is:", device.bank_id
	    print "\nThe first known Bank ID is:", check, "\n"
	    return False 
    return True

"""
The main function
Have 3 options:
1: Manually enter json and dev files
2: Put the json and dev files as parameters
3: Put a directory and the json/dev files as a parameter to hold all the files 
Creates the tb, dev, cfg, and vman file (for a directory only)
"""
def dynamic_file_development():
    complete = False
    valid_json = None

    if len(sys.argv) == 1:
        print "\nEnter the JSON file and then enter the DEV file when asked.\nMake sure your JSON file is valid!\n"
        correctJson = False
        while not(correctJson):
      	    valid_json = available_json_file()
      	    if (type(valid_json) is str) or valid_json == -1:
      	        correctJson = True

    elif len(sys.argv) <= 4 and len(sys.argv) != 2:
	print "\nJSON file entered:", sys.argv[1]
        valid_json = available_json_file(sys.argv[1])

    else:
	print "\nDon't have the right amount of parameters!"
	print "May type:\n\"python <project.py>\" (Manual)"
	print "\"python <project.py> <jsonFile.json> <devFile.dev>\" (Pre-set filenames)"
	print "\"python <project.py> <jsonFile.json> <devFile.dev> <directory_name>\" (Directory to hold files)"
	return 

    if (type(valid_json) is str):
	testbed_files = None
	#creates file generator with or without a directory depending on parameters
	if len(sys.argv) == 4:
	    testbed_files = file_generator(sys.argv[3])
	else:
	    testbed_files = file_generator()
        json_file = open(valid_json, "r")
        json_string = json_file.read()
        print "\nJSON file found!\n"
        data = json.loads(json_string)
        device_list = list(data)
        device_list.sort()
        device_file = dev_file(data)
	#adding device objects to dev file list of devices
        for device in device_list:
	    match = re.match("extra", device, re.I)
	    if match:
		extra_list = list(data[match.group()])
		for extra in extra_list:
		    new_device = device_object(device_file)
		    new_device.set_device(extra, data[match.group()][extra], data)
		    #extra devices not going to be printed to dev file unless added with add_device()
		    device_file.extra_list.append(new_device)
		    #device_file.add_device(new_device)
	    else:
    	        new_device = device_object(device_file)
                new_device.set_device(device, data[device], data)
                device_file.add_device(new_device)

	#sets devices in order, with database values, etc.
	for device in device_file.device_list:
	    device_file.set_main_dynamic_dict(device)
	    device_file.set_software_dynamic_dict(device)

	for device in device_file.device_list:
            device.set_rolename()
            device.set_admin_ip()

	device_file.move_xconnect_to_top()
	device_file.sort_aps()
	device_file.move_local_to_top()
        device_file.move_master_to_top()

	device_file.set_local() 
	device_file.set_standby()

	#makes sure all the devices have the same bank id
        if check_bank_id(device_file): 
	    availability = False

	    #different available_dev_file depending on amount of parameters
	    if len(sys.argv) == 1:
		correct = False       
    	        while not(correct):
    		    availability = available_dev_file(device_file)
    	            if availability == True or availability == -1: 
    	                correct = True
		    else:
		        print "\nUnable to create file\n"

	    elif len(sys.argv) == 3:
		print "Dev file entered:", sys.argv[2]
		availability = available_dev_file(device_file, sys.argv[2])

	    elif len(sys.argv) == 4:
		print "Dev file entered:", sys.argv[2]
                availability = available_dev_file(device_file, sys.argv[2], sys.argv[3])
	    
	    #if device_file has a valid path 
	    if availability == True:
		#sets up the tb file, adds it to generator
		#tb_path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/qa/automation/configs/tb/"+ device_file.testbed_name + ".tb"
		tb_path = "/home/" + pwd.getpwuid(os.getuid()).pw_name + "/" + device_file.testbed_name + ".tb"
		#adds extra devices to tb file
		tb_file = tb(tb_path, (device_file.device_list + device_file.extra_list), device_file.filename)
		tb_file.filename = device_file.testbed_name + ".tb" 
		testbed_files.set_tb_file(tb_file)
		testbed_files.write_tb_file()

		#adds dev file to generator
		testbed_files.set_dev_file(device_file)
		testbed_files.write_dev_file()

		#adds cfg files to generator
		for device in device_file.device_list:
                    if device.cfg != None:
			testbed_files.set_cfg_files(device.cfg)
		testbed_files.write_cfg_files()
	
		#generates vman file if directory is present
		testbed_files.set_vman_file()

		device_file.end_operations()
		complete = True
	    elif availability == -1:
		print "Exit, unable to create file\n" 
	    else:
	        print "\nUnable to create file\n"
        else:
            print "Bank IDs are different, unable to create file!\n"
    else:
	print "Unable to create file\n"
    return complete

dynamic_file_development()
