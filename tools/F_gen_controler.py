#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 23 09:27:10 2019

@author: seeger01
"""
#this script should be used to controal an RIGOL DG4162 FGen
# wire shark debung filter options (ip.src == 192.168.2.3 || ip.dst == 192.168.2.3 ) && !(tcp.flags.ack && tcp.len <= 1)
import pyvisa #pip install -U pyvisa-py
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage.filters import gaussian_filter
import warnings
rm = pyvisa.ResourceManager()


class DG4xxx:

    def __init__(self,rm,IP):

        self.params={'IP':IP}
        self.rm=rm
        self.visa=self.rm.open_resource('TCPIP0::'+IP+'::INSTR')
        self.visa.timeout=10000
        retval=self.visa.query('*IDN?')
        self.params['IP']
        self.params['Vendor']=retval.split(",")[0]
        self.params['Type']=retval.split(",")[1]
        self.params['SN']=retval.split(",")[2]
        self.params['FWVersion']=retval.split(",")[3].replace('\n', '')

    def queryCommand(self,CMD):
        return self.visa.query(CMD)

    def sendCommand(self,CMD):
        return self.visa.write(CMD)

    def fiereBurst(self,freq,ampl,offset,phase,cycles,channel=1,delay=False):
        minAmpl=-ampl/2+offset
        maxAmpl=ampl/2+offset
        if(minAmpl<0):
            raise ValueError('Output voltage should never be negative but is at minium '+str(minAmpl))
        if(maxAmpl>5):
            raise ValueError('Output voltage should never be grater than 5 Volt but is at max '+str(maxAmpl))
        if(freq<0.001):
            raise ValueError('Output frequency is to low (<1 mHz) or negative')
        self.sendCommand(':OUTPut'+str(channel)+':STATe OFF')
        self.sendCommand(':SOURce'+str(channel)+':APPLy:SINusoid '+str(freq)+','+str(ampl)+','+str(offset)+','+str(phase))
        self.sendCommand(':SOURce'+str(channel)+':BURSt:NCYCles '+str(cycles))
        self.sendCommand(':SOURce'+str(channel)+':BURSt:TRIGger:SOURce MANual') #activate manual TRIGger
        self.sendCommand(':SOURce'+str(channel)+':BURSt ON')#activate burst mode
        self.sendCommand(':OUTPut'+str(channel)+':STATe ON')
        self.sendCommand(':SOURce'+str(channel)+':BURSt:TRIGger')
        if delay:
            Duration=1/freq*cycles
            print("Burst Duration="+str(Duration)+' seconds \nsleeping this time')
            time.sleep(Duration)
            self.sendCommand(':OUTPut OFF')
            return
        else:
            return

    def ArmExtTrigSyncburst(self,freq,ampl,offset,phase,cycles,CH2Freq,CH2Cycles):
        #this function configures the function generator to output a sin signal with configured phase amplitude and frequency on CH1.
        #CH2 generates a synchronous square wave signal with adjustable frequency and 180 phase shift.
        #At t=0 no square pulse is generated.
        #the display of the function generator couldbe misleading
        self.sendCommand(':OUTPut1:STATe ON') #
        self.sendCommand(':SOURce1:APPLy:SINusoid '+str(freq)+','+str(ampl)+','+str(offset)+','+str(phase))
        self.sendCommand(':SOURce2:APPLy:SQUare '+str(CH2Freq)+',3,1.5,0')#phase is ignored in burst mode and has to be set seperate
        self.sendCommand(':SOURce1:BURSt ON')#activate burst mode
        self.sendCommand(':SOURce2:BURSt ON')#activate burst mode
        self.sendCommand(':SOURce2:BURSt:PHASe 180')#activate burst mode
        self.sendCommand(':SOURce1:BURSt:MODE TRIGgered')
        self.sendCommand(':SOURce2:BURSt:MODE TRIGgered ')
        self.sendCommand(':SOURce1:BURSt:NCYCles '+str(cycles))
        self.sendCommand(':SOURce2:BURSt:NCYCles '+str(CH2Cycles))
        self.sendCommand(':SOURce1:BURSt:TRIGger:SOURce EXTernal')
        self.sendCommand(':SOURce2:BURSt:TRIGger:SOURce EXTernal')
        self.sendCommand(':OUTPut1:STATe ON') #
        self.sendCommand(':OUTPut2:STATe ON')
        return

class MSO5xxx:

    def __init__(self,rm,IP):

        self.params={'IP':IP}
        self.rm=rm
        self.visa=self.rm.open_resource('TCPIP0::'+IP+'::INSTR')
        self.visa.timeout=10000
        retval=self.visa.query('*IDN?')
        self.params['IP']
        self.params['Vendor']=retval.split(",")[0]
        self.params['Type']=retval.split(",")[1]
        self.params['SN']=retval.split(",")[2]
        self.params['FWVersion']=retval.split(",")[3].replace('\n', '')
        print("Init Done Device is")
        print(self.params)
        
    
    def queryCommand(self,CMD):
        return self.visa.query(CMD)

    def sendCommand(self,CMD):
        return self.visa.write(CMD)
    
    def run(self):
        return self.visa.write(":RUN")
    
    def stop(self):
        return self.visa.write(":STOP")
    
    def single(self):
        return self.visa.write(":SINGle")
    
    def forceTrigger(self):
        return self.visa.write(":TFORce")
    
    def configCannels(self,memdepth=1e4):
        self.run()
        self.params['Memdepth']=memdepth
        self.visa.write(':ACQuire:MDEPth '+str(int(self.params['Memdepth'])))
        print(':ACQuire:MDEPth '+str(int(self.params['Memdepth'])))
        self.params['Memdepth']=float(self.visa.query(":ACQuire:MDEPth?")) 
        print("Memorydeph is "+str(self.params['Memdepth'])+' should be set to '+str(memdepth))
        self.params['Samplerate']=float(self.visa.query(":ACQuire:SRATe?"))
        print("Samplerate is "+str(self.params['Samplerate']))
        self.stop()
        

    def getWaveForm(self,Channel,chunklen=1e4):
        MAXVISATRYES=10
        #cativate cahnnel 1
        if(Channel==1):
            self.sendCommand(":WAVeform:SOURce CHANnel1")
        if(Channel==2):
            self.sendCommand(":WAVeform:SOURce CHANnel2")
        #change mode RAW
        self.sendCommand(":WAVeform:FORMat RAW")
        self.sendCommand(":WAVeform:MODE RAW")
        #read data configuration for active channel
        DataFormatCodes={0:'BYTE',1:'WORD',2:'ASCii'}
        DataTypeCodes={0:'NORMal',1:'MAXimum',2:'RAW'}
        peramble=self.queryCommand(":WAVeform:PREamble?")
        Peramblearray=np.fromstring(peramble[:-1],dtype = np.float,sep =',')
        DataParams={'Format' : DataFormatCodes[int(Peramblearray[0])],
                    'Type':DataTypeCodes[int(Peramblearray[1])],
                    'Points':Peramblearray[2],
                    'Averages':Peramblearray[3],
                    'DeltaX':Peramblearray[4],
                    'X0':Peramblearray[5],
                    'Xreference':Peramblearray[6],
                    'DeltaY':Peramblearray[7],
                    'Y0':Peramblearray[8],
                    'Yreference':Peramblearray[9]}
        print(DataParams)
        #calculate params for chunked data reading 
        length=DataParams['Points']
        lastchunklen=length%chunklen
        loopcount=int(np.floor(length/chunklen))
        tmp=np.zeros(int(length))
        for i in range(loopcount):
            startidx=int(i*chunklen+1)#SCPI index starts at 1
            strstartidx=str(startidx)
            stopidx=int(startidx+chunklen-1)
            strstopidx=str(stopidx)
            self.sendCommand("WAV:START "+strstartidx)
            time.sleep(0.01)
            self.sendCommand("WAV:STOP "+strstopidx)
            time.sleep(0.01)
            print("getting DATA FROM "+strstartidx+' to '+strstopidx)
            retrycount=0
            while (retrycount<MAXVISATRYES):
                try:
                    raw=self.visa.query_binary_values(":WAVeform:DATA?",datatype='B', is_big_endian=False)
                    break
                except:
                    retrycount=retrycount+1
                    print("VISA ERROR Retrying")
                
            tmp[(startidx-1):(stopidx)]=np.asarray(raw)
            
        #first value has preamble in it  '#9000014000+2.024370E-01' remove this
        #look for index of + or - and take first occurence
        DataArray=(tmp-DataParams['Yreference']-DataParams['Y0'])*DataParams['DeltaY']
        return DataArray,DataParams
    
def CalculateExtTODelay(CH2Data,CH2Conf):
    #this function asuses that the gtrigger Output of the scope is connected to CH2 Input
    
    #using gausfilter for smothing the rising edge of ch2 signal with distorting the zeropoint by aprox 2 datapoints
    # Endpoint mode default is ‘reflect’
    smoothed= gaussian_filter(CH2Data,sigma=5)
    #calulating gradient 
    smootheddiff=np.gradient(smoothed)
    diff=np.gradient(CH2Data)
    # get maximum of gradient
    smoothedmax=np.argmax(smootheddiff)
    normalmax=np.argmax(diff)
    if abs(smoothedmax-normalmax)>10:
        warnings.warn("Smothed and un smoothed maximum differ a lot maybe the data has spkes in it",RuntimeWarning)
    TimeDleay=(normalmax-CH2Conf['Points']/2)*CH2Conf['DeltaX']
    return TimeDleay
    
    
    
def generateXValues(CHConf):
    #The Trigger condition is flase at Points/2 (eg 5e5) and True at Points/2+1Sample (eg 500001)        
    #therefore Points/2+1 (500001) is the Zero Point in Time
    # ignoring X0 and X reference at the moment
    Points=(np.arange(CHConf['Points'])-CHConf['Points']/2)*CHConf['DeltaX']
    return Points

def PlotDualWaveform(CH1Data,CH1Conf,CH2Data,CH2Conf):
        CH1Xvalues=generateXValues(CH1Conf)
        CH2Xvalues=generateXValues(CH2Conf)
        fig, ax = plt.subplots()
        ax.set_title('Data From Scope')
        ax.set_ylabel('Voltage in V')
        ax.set_xlabel('Time in s')
        ax.plot(CH1Xvalues,CH1Data,label='Channel 1')
        ax.plot(CH2Xvalues,CH2Data,label='Channel 2')
        ax.grid()
        ax.legend()
        fig.show()
        

def GetScopeExtriggerDelay(scope,Wavefomnumber):
    counts =np.arange(Wavefomnumber)
    delays=np.zeros(Wavefomnumber)
    for i in counts: 
        scope.single()
        time.sleep(0.5)
        CH2Data,CH2Conf=scope.getWaveForm(2)        
        delays[i]=CalculateExtTODelay(CH2Data,CH2Conf)
    mean=np.mean(delays)
    std=np.std(delays)
    CH1Data,CH1Conf=scope.getWaveForm(1)
    CH2Data,CH2Conf=scope.getWaveForm(2)
    PlotDualWaveform(CH1Data,CH1Conf,CH2Data,CH2Conf)

def Fireloop(FGEN):
    for x in range(0, 20):
        FGEN.fiereDifferentialBurst(100.0,0.01,0.005,0,10,True)
