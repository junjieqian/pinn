#!/usr/bin/env python

# logreader for non group_reporting logs

import string
import os
import sys
import csv
import numpy as np

class threadreader:
  _workload = {}
  _perf_path = ""
  _iostat_path = ""
  _workload_filename = ""
  _blocksize = ""

  def __init__(self, workload_filename, perf_path, iostat_path):
    # @param workload_filename, the defination of the workload run
    # @param perf_path, the fio log files
    # @param iostat_path, the io stat files
    self._perf_path = perf_path
    self._iostat_path = iostat_path
    self._workload_filename = workload_filename
    with open(self._workload_filename, 'rU') as csvreader:
      workloads = csv.reader(csvreader, delimiter=',', quotechar='|')
      for row in workloads:
        if "Test id" in row:
          continue
        else:
          _testnum = row[0]
          _filesize = row[1]
          self._blocksize = row[2]
          _patern = row[3]
          _access_list = _patern.split()
          _runtime = row[4]
          _ramptime = row[5]
          _startdelay = row[6]
          _workers = row[7]
          _iodepth = row[8]
          _device_num = len(row[9].split(":"))
          self._workload[_testnum] = row[1:2]
          self._workload[_testnum].append(_access_list)
          self._workload[_testnum].append(row[4:8])
          self._workload[_testnum].append(str(_device_num))

  def perf_read(self):
    if not os.path.isdir(self._perf_path):
      return
    ret = csv.writer(open("fiolog_threads.csv", "wb"))
    ret.writerow(["testnum", "iops", "disk utilization", "average bandwidth", "minimal thread time", "1/4 thead time", "1/2 thread time", "3/4 thread time", "maximum thread time"])
    for roots, dirs, files in os.walk(self._perf_path):
      files.sort(key=lambda x:int(x.split('.')[0]))
      for f in [os.path.join(roots, fs) for fs in files]:
        fp = open(f)
        count = 0
        _iops = 0.0
        _throughput = 0.0
        _disk_utilization = 0.0
        _cpu_user = 0.0
        _cpu_system = 0.0
        _context_switches = 0.0
        _average_bandwidth = 0.0
        _write_submission_latency = 0.0
        _write_completion_latency = 0.0
        _read_submission_latency = 0.0
        _read_completion_latency = 0.0
        _dev_id1 = -1
        _runtime = []
        for line in fp:
          if not "fio-2.1.3" in line:
            continue
          word = line.split(";")
          _dev_id1 = word.index("nvme0n1")
          count += 1
          _runtime.append(float(word[8]) + float(word[49])) # msec, the runtime for one thread
          _testnum = word[2]
          _iops += (float(word[7]) + float(word[48]))/2.0
          _throughput += _iops * int(self._blocksize.split('K')[0])
          if line.find("nvme1n1") < 0:
            _disk_utilization += float(word[-1].split('\n')[0].strip('%'))
          else:
            if line.find("nvme2n1") < 0:
              _disk_utilization += (float(word[_dev_id1 + 8].strip('%')) + float(word[_dev_id1 + 17].split('\n')[0].strip('%')))/2.0
            else:
              _disk_utilization += (float(word[_dev_id1 + 8].strip('%')) + float(word[_dev_id1 + 17].strip('%')) + float(word[_dev_id1 + 26].strip('%')) + float(word[_dev_id1 + 35].split('\n')[0].strip('%')))/4.0
          _cpu_user += float(word[87].strip('%'))
          _cpu_system += float(word[88].strip('%'))
          _context_switches += float(word[89])
          _average_bandwidth += (int(word[6])+int(word[47]))/2.0
          _write_submission_latency += float(word[52])
          _write_completion_latency += float(word[56])
          _read_submission_latency  += float(word[11])
          _read_completion_latency  += float(word[15])
        _runtime_np = np.array(_runtime)
        if count == 0:
          continue
        ret.writerow([_testnum, str(_iops/count), str(_disk_utilization/count), str(_average_bandwidth/count), str(min(_runtime)), str(np.percentile(_runtime_np, 25)), str(np.percentile(_runtime_np, 50)), str(np.percentile(_runtime_np, 75)), str(max(_runtime))])
        fp.close()

  def iostat_read(self):
    if not os.path.isdir(self._iostat_path):
      return
    ret = csv.writer(open("iostatlog.csv", "wb"))
    ret.writerow(["testnum", "software layer", "io wait"])
    # start time needs to be modified according to the system boot time
    # _boot_time format, [month, day, hour, minutes, seconds]
    _boot_time = [4, 15, 10, 25, 9]
    _cur_time  = [0, 0, 0, 0, 0]
    for roots, dirs, files in os.walk(self._iostat_path):
      _timestamp_flag = False
      _data_flag = False
      files.sort()
      for f in files:
        _testnum = f.split()[-1]
        fp = open(os.path.join(roots, f))
        _timestamp_flag = False
        _data_flag = False
        _before_flag = False
        _before_time = 0
        _after_time = 0
        _before_software_layer = 0.0
        _after_software_layer = 0.0
        _before_io_wait = 0.0
        _after_io_wait = 0.0
        for line in fp:
          if line.find("/2015")>=0 and not 'Linux' in line and not _timestamp_flag:
            _cur_time[0] = int(line.split()[0].split('/')[0])
            _cur_time[1] = int(line.split()[0].split('/')[1])
            _cur_time[2] = (int(line.split()[1].split(':')[0]) + 12) if "PM" in line.split()[2] else int(line.split()[1].split(':')[0])
            _cur_time[3] = int(line.split()[1].split(':')[1])
            _cur_time[4] = int(line.split()[1].split(':')[2])
            _before_time = 2592000 * (_cur_time[0] - _boot_time[0]) + 86400 * (_cur_time[1] - _boot_time[1]) + 3600 * (_cur_time[2] - _boot_time[2]) + 60 * (_cur_time[3] - _boot_time[3]) + (_cur_time[4])
            _timestamp_flag = True
            continue
          if line.find("/2015")>=0 and not 'Linux' in line and _timestamp_flag:
            _cur_time[0] = int(line.split()[0].split('/')[0])
            _cur_time[1] = int(line.split()[0].split('/')[1])
            _cur_time[2] = (int(line.split()[1].split(':')[0]) + 12) if "PM" in line.split()[2] else int(line.split()[1].split(':')[0])
            _cur_time[3] = int(line.split()[1].split(':')[1])
            _cur_time[4] = int(line.split()[1].split(':')[2])
            _after_time = 2592000 * (_cur_time[0] - _boot_time[0]) + 86400 * (_cur_time[1] - _boot_time[1]) + 3600 * (_cur_time[2] - _boot_time[2]) + 60 * (_cur_time[3] - _boot_time[3]) + (_cur_time[4])
            _timestamp_flag = False
          if line.find("avg-cpu")>=0 and not _data_flag:
            _data_flag = True
            continue
          if _data_flag:
            if not _before_flag: # this is before data
              _before_flag = True
              _before_software_layer = float(line.split()[0]) + float(line.split()[2])/100.0
              _before_io_wait = float(line.split()[3])/100.0
              _before_idle_time = float(line.split()[5])/100.0
              _data_flag = False
            else:
              _before_flag = False
              _after_software_layer = float(line.split()[0]) + float(line.split()[2])/100.0
              _after_io_wait = float(line.split()[3])/100.0
              _after_idle_time = float(line.split()[5])/100.0
              _data_flag = False
        _software_time = _after_software_layer * _after_time - _before_software_layer * _before_time
        _io_wait = _after_io_wait * _after_time - _before_io_wait * _before_time
        _idle_time = _after_idle_time * _after_time - _before_idle_time * _before_time
        _cpu_utilization = _software_time/(_after_time - _before_time)
        ret.writerow([_testnum, _cpu_utilization])
        fp.close()
