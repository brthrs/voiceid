#!/usr/bin/env python
#########################################################################
#
# VoiceID, Copyright (C) 2011, Sardegna Ricerche.
# Email: labcontdigit@sardegnaricerche.it, michela.fancello@crs4.it, 
#        mauro.mereu@crs4.it
# Web: http://code.google.com/p/voiceid
# Authors: Michela Fancello, Mauro Mereu
#
# This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#########################################################################
#
# VoiceID is a speaker recognition/identification system written in Python,
# based on the LIUM Speaker Diarization framework.
#
# VoiceID can process video or audio files to identify in which slices of 
# time there is a person speaking (diarization); then it examines all those
# segments to identify who is speaking. To do so you must have a voice models
# database. To create the database you have to do a "train phase", in
# interactive mode, by assigning a label to the unknown speakers.
# You can also build yourself the speaker models and put those in the db
# using the scripts to create the gmm files.

from threading import Thread
from voiceid import *
from voiceid.db import GMMVoiceDB
from voiceid.sr import Voiceid
from wx.lib.intctrl import IntCtrl
from wx.lib.pubsub import Publisher
import MplayerCtrl as mpc
import os
import pyaudio
import shutil
import time
import wave
import wx
import wx.lib.buttons as buttons

#-------------------------------------
# initializations and global variables
#-------------------------------------
dirName = os.path.dirname(os.path.abspath(__file__))
bitmapDir = os.path.join(dirName, 'bitmaps')
OK_DIALOG = 33
CANCEL_DIALOG = 34
MAX_TIME_TRAIN = 30
PARTIAL_TIME = 5
CONFIGURATION = 1
THRESHOLD = -32.16
class Controller:
    """A class that represents a controller between the views (CentralPanel and MainFrame) and model data management (Models) """
    
    def __init__(self, app):
        self.model = Model()
        self.model.attach(self)
        self.frame = MainFrame()
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.central_panel = None
        self.frame.SetSizer(self.sizer)
        self.frame.Layout()
        self.config_check = -1
        self.frame.Bind(wx.EVT_MENU, lambda event: self.create_central_panel(event, False), self.frame.training_rec_menu_item)
        self.frame.Bind(wx.EVT_MENU, lambda event: self.create_central_panel(event, True), self.frame.start_rec_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.create_dialog_max_time, self.frame.max_time_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.create_dialog_partial_time, self.frame.partial_time_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.create_dialog_partial_time, self.frame.sett3)
        Publisher().subscribe(self.update_status, "update_status")
        Publisher().subscribe(self.create_dialog_speaker_name, "crea_dialog")
        Publisher().subscribe(self.update_speakers_list, "update_speakers_list")
        Publisher().subscribe(self.clear_speakers_list, "clear_speakers_list")
        Publisher().subscribe(self.toogle_stop_button, "toogle_button")

    def create_central_panel(self,event,test_mode):
        """ Create a central panel for displaying data """
        if not self.central_panel == None:
            self.sizer.Clear()
            self.sizer.Detach(self.central_panel) 
            
        self.model.set_test_mode(test_mode) 
        
        self.central_panel = MainPanel(self.frame, test_mode)
        
        self.sizer.Insert(1,self.central_panel, 5, wx.EXPAND)

        self.central_panel.recordButton.Bind(wx.EVT_BUTTON, self.on_rec)
        self.central_panel.pauseButton.Bind(wx.EVT_BUTTON, self.on_pause)
        if test_mode == False:
            self.central_panel.time = MAX_TIME_TRAIN
            wx.CallAfter(Publisher().sendMessage, "update_status", "Read the following paragraph ")
        else:
            self.central_panel.pauseButton.Show()
            wx.CallAfter(Publisher().sendMessage, "update_status", "Speak in a natural way chanting the words properly ")
        
        self.sizer.Layout()
        self.frame.Layout()
        
    def on_rec(self,event):  
        """ Start record process """ 
        
        self.total_computing_time = 0
        self.central_panel.toggle_record_button()
        if self.model.get_test_mode() == True:
            self.central_panel.time = 0
            self.central_panel.textList.Clear()
            self.config_check = -1
            if self.frame.sett1.IsChecked():
                self.config_check = 1
                self.model.start_record(conf = self.config_check, partial_seconds = PARTIAL_TIME)
            elif self.frame.sett2.IsChecked():
                self.config_check = 2
                self.model.start_record(conf = self.config_check, partial_seconds = PARTIAL_TIME)
            else:
                self.config_check = 3
                self.model.start_record(conf = self.config_check, partial_seconds = PARTIAL_TIME, stop_callback = self.on_pause)
            self.total_computing_time = time.time()
        else:
            self.model.start_record(total_seconds = MAX_TIME_TRAIN, stop_callback = self.on_pause, save_callback = self.open_dialog)
            self.central_panel.time = MAX_TIME_TRAIN
            
        self.central_panel.timer.Start(1000)
        wx.CallAfter(Publisher().sendMessage, "update_status", "Recording ... ")
        
        
    def on_pause(self,event=None):  
        """ Stop record process """  
        
        def wait_stop(test_mode):
            if not self.frame.sett3.IsChecked(): self.model.stop_record()
            wx.CallAfter(Publisher().sendMessage, "update_status", "Wait for updates ... ") 
            while not self.model.get_process_status() or self.model.is_process_running():
                time.sleep(2)
            best = self.model.get_last_result()[0]
            wx.CallAfter(Publisher().sendMessage, "toogle_button", "toogle_stop")
            self.total_computing_time = time.time() - self.total_computing_time    
            wx.CallAfter(Publisher().sendMessage, "update_status", "Best speaker is "+best[0]+" found in "+str(int(self.total_computing_time))+" seconds")
        if  self.model.get_test_mode() == True:
            self.t = Thread(target=wait_stop, args=(True,))
            self.t.start()
        else:
            
            self.central_panel.toggle_stop_button()

        self.central_panel.timer.Stop()
        
        
    def toogle_stop_button(self,msg):
        self.central_panel.toggle_stop_button()
    
    
    def open_dialog(self, file_):
        """
        Open input dialog to insert speaker name
        """
        wx.Bell()
        wx.CallAfter(Publisher().sendMessage, "update_status", "Insert speaker's name ... ")
        wx.CallAfter(Publisher().sendMessage, "crea_dialog",file_)
        
    def create_dialog_speaker_name(self, file_):
        
        self.cluster_form = ClusterForm(self.frame, "Edit cluster speaker",label = "Speaker name:" )
        
        self.cluster_form.Bind(wx.EVT_BUTTON, lambda event: self.set_speaker_name(event,str(file_.data)))
        self.cluster_form.Layout()
        self.cluster_form.ShowModal()


    def set_speaker_name(self, event, file_):
        
        wx.CallAfter(Publisher().sendMessage, "update_status", "Wait for db updates ... ") 
        
        if event.GetId() == CANCEL_DIALOG:
            self.cluster_form.Destroy()
            wx.CallAfter(Publisher().sendMessage, "update_status", "Read the following paragraph")
            return
    
        if event.GetId() == OK_DIALOG:
            speaker = self.cluster_form.tc1.GetValue()
            if not len(speaker) == 0: 
                if self.model.set_speaker_name(speaker, file_) == True:
                    wx.CallAfter(Publisher().sendMessage, "update_status", "Speaker added in db")
                else:
                    wx.CallAfter(Publisher().sendMessage, "update_status", "Error adding speaker in db")   
            self.cluster_form.Destroy()
            
    def update_status(self, msg):
        """
        Receives data from thread and updates the status bar
        """
        t = msg.data
        
        self.frame.set_status_text(t)

    def update(self):
        """ Update speaker's list  """
        
        if self.model.get_test_mode() == True:
            result = self.model.get_last_result()
            if result != None:
                i = 0
                wx.CallAfter(Publisher().sendMessage, "clear_speakers_list", "") 
                for r in result:
                    i+=1
                    if self.config_check == 1:
                        name = r[0]
#                        if r[1] < THRESHOLD:
#                            name = "Unknown"
                    wx.CallAfter(Publisher().sendMessage, "update_speakers_list", str(i)+" "+name+" score: "+str(r[1])) 
     
    

    def clear_speakers_list(self, msg):
        self.central_panel.textList.Clear()
        
    def update_speakers_list(self, data_speaker):
        text = data_speaker.data
        try:
            self.central_panel.textList.Append(text)    
        except IOError:
            print "MainPanel is not in testing multiple_waves_mode"
    
 
    def create_dialog_max_time(self, event):
        
        self.setting_form = ClusterForm(self.frame, "Set max time", label = "Time:")
        self.setting_form.Bind(wx.EVT_BUTTON, self.set_max_time_train)
        self.setting_form.tc1.Hide()
        self.setting_form.max.Show()
        self.setting_form.max.ChangeValue(str(MAX_TIME_TRAIN))
        self.setting_form.Layout()
        self.setting_form.ShowModal()  
           
    def create_dialog_partial_time(self, event):
        self.partial_time = ClusterForm(self.frame, "Set time", label = "Time:")
        self.partial_time.Bind(wx.EVT_BUTTON, self.set_partial_time)
        self.partial_time.tc1.Hide()
        self.partial_time.max.Show()
        self.partial_time.max.ChangeValue(str(PARTIAL_TIME))
        self.partial_time.Layout()
        self.partial_time.ShowModal()
    
    def set_max_time_train(self, event):
        if event.GetId() == CANCEL_DIALOG:
            self.setting_form.Destroy()
            return
    
        if event.GetId() == OK_DIALOG:
            t = self.setting_form.max.GetValue()
            if t: 
                global MAX_TIME_TRAIN
                MAX_TIME_TRAIN = t

                if self.central_panel != None:
                    self.central_panel.time = MAX_TIME_TRAIN

            self.setting_form.Destroy()
            
    def set_partial_time(self, event):
        if event.GetId() == CANCEL_DIALOG:
            self.partial_time.Destroy()
            return
    
        if event.GetId() == OK_DIALOG:
            t = self.partial_time.max.GetValue()
            if t: 
                global PARTIAL_TIME
                PARTIAL_TIME = t

            self.partial_time.Destroy()         
        

class Record():
    """
    A class that represents the management and the creation of a recording
    """
    def __init__(self, wave_prefix, total_seconds=-1, partial_seconds=None, incremental_mode = True, stop_callback=None, save_callback=None):
        self.chunk = 1600
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.partial_seconds = partial_seconds
        self.record_seconds = total_seconds
        self.wave_prefix = wave_prefix
        self.data = None
        self.stream = None
        self.p = pyaudio.PyAudio()
        if partial_seconds != None and partial_seconds > 0:
            self.multiple_waves_mode = True
            
        else: self.multiple_waves_mode = False
        
        self.incremental_mode = incremental_mode

        self._stop_signal = True
        self.stop_callback = stop_callback
        self.save_callback = save_callback
        
    def start(self):
        """ Start a thread to recording """
        self._stop_signal = False
        self.thread_logger = Thread(target=self._rec)
        self.thread_logger.start()
        
    def _rec(self):
        """ Record the incoming audio """
        self.stream = self.p.open(format = self.format,
               channels = self.channels,
               rate = self.rate,
               input = True,
               frames_per_buffer = self.chunk)
        all_ = []
        i=0
        while  self.is_recording():
            try:
                self.data = self.stream.read(self.chunk)
                all_.append(self.data)
            
                current = float(i) * float(self.chunk) / float(self.rate)
                #multiple mode
                if self.multiple_waves_mode == True and current>0 and ( current % self.partial_seconds ) == 0:
                    self.thread_rec = Thread(target=self.save_wave, args =(all_,str(int(current))))
                    self.thread_rec.start()
                    if self.record_seconds > 0 and current >= self.record_seconds:
                        self.stop()
                #single mode    
                if not self.multiple_waves_mode  and self.record_seconds != None :
                    if  current >= self.record_seconds:
                        self.thread_rec = Thread(target=self.save_wave, args =(all_,""))
                        self.thread_rec.start()
                        self.stop()
                i += 1
            except IOError:
                print "warning: dropped frame"
               
         
    def is_recording(self):  
        """ Return true if recording """ 
         
        return not self._stop_signal 
    
    def stop(self):
        """ Stop the record"""
        self._stop_signal = True
        if self.stop_callback != None:
            self.stop_callback()
        time.sleep(1)
        self.stream.close()
        self.p.terminate()
    
    def save_wave(self, all_, suffix):
        """ Write record data to WAVE file """
        
        name = self.wave_prefix + suffix +".wav"
        if self.incremental_mode:
            data = ''.join(all_)
        else: 
            data = ''.join(all_[-int(float(16000*self.partial_seconds) / float(self.chunk)):])
        
        wf = wave.open(name, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(data)
        wf.close()
        if self.save_callback:
            self.save_callback(name)
    

class MainFrame(wx.Frame):
    """ Frame containing all GUI components """
    def __init__(self):
        wx.Frame.__init__(self, None, title="Voiceid", size=(600, 500))
        self._create_menu()
        self.sb = self.CreateStatusBar()
        self.Show()

    def _create_menu(self):
        """
        Creates a menu
        """
        menubar = wx.MenuBar()
        trainingMenu = wx.Menu()
        srMenu = wx.Menu()
        #settMenu = wx.Menu()
        testsMenu = wx.Menu()
        self.training_rec_menu_item = trainingMenu.Append(wx.NewId(), "&New", "New")
        self.max_time_menu_item = trainingMenu.Append(wx.NewId(), "&Edit max time", "Edit max time")
        self.start_rec_menu_item = srMenu.Append(wx.NewId(), "&Start", "Start")
        self.partial_time_menu_item = srMenu.Append(wx.NewId(), "&Edit partial time", "Edit partial time")
        self.sett1 = testsMenu.Append(wx.NewId(), "&Incremental", "Incremental",kind=wx.ITEM_RADIO )
        self.sett2 = testsMenu.Append(wx.NewId(), "&Fixed", "Fixed",kind=wx.ITEM_RADIO )
        self.sett3 = testsMenu.Append(wx.NewId(), "&One shot", "One shot",kind=wx.ITEM_RADIO )
        
        self.sett2.Enable(True)
        self.sett3.Enable(True)
        
        testsMenu.Check(self.sett1.GetId(), True)
        testsMenu.Check(self.sett2.GetId(), False)
        
        menubar.Append(trainingMenu, '&Training')
        menubar.Append(srMenu, '&Test')
        menubar.Append(testsMenu, '&Settings')
        
        #menubar.Append(settMenu, '&Settings')
        self.SetMenuBar(menubar)
        
    def set_status_text(self, text):
        """ Update the status-bar text """
        #TODO: set status text
        self.sb.SetStatusText(text)

    
        
class MainPanel(wx.Panel):
    """ A panel containing a window to write input/output info and control's buttons """
    
    def __init__(self, parent, test_mode):
        wx.Panel.__init__(self, parent, -1,size=(500, 400))
        
        self.parent = parent
        
        self.test_mode = test_mode
        
        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.textRead = None
        
        self.textList = None
        
        self.staticText = None
        
        Publisher().subscribe(self.set_time_label, "update_timer")
       
        
        self.font = wx.Font(15, wx.SWISS, wx.NORMAL, wx.NORMAL, False, u'Comic Sans MS')
        if not self.test_mode:
             
             
            self.staticText = wx.StaticText(self, wx.ID_ANY, label="TRAINING MODE", style=wx.ALIGN_CENTER)
            
            self.textRead = wx.TextCtrl(self, size=(450, 320),  style=wx.TE_MULTILINE)
             
            text = """La Sardegna, la seconda isola piu' estesa del mar Mediterraneo dopo la Sicilia (ottava in Europa e la quarantottesima nel mondo) e' una regione italiana a statuto speciale denominata Regione Autonoma della Sardegna.
Lo Statuto Speciale, sancito nella Costituzione del 1948, garantisce l'autonomia amministrativa delle istituzioni locali a tutela delle peculiarita' etno-linguistiche e geografiche.
Nonostante l' insularita attenuata solo alla vincinanza della Corsica, la posizione strategica al centro del mar Mediterraneo occidentale, ha favorito sin dall'antichita' i rapporti commerciali e culturali, come gli interessi economici, militari e strategici. In epoca moderna molti viaggiatori e scrittori hanno esaltato la bellezza della Sardegna,
immersa in un ambiente ancora incontaminato con diversi endemismi e in un paesaggio che ospita le vestigia della civilta' nuragica."""
                 
            font_text = wx.Font(13, wx.SWISS, wx.NORMAL, wx.NORMAL, False, u'Arial')    
            self.textRead.AppendText(text)
            self.textRead.SetFont(font_text)
            hbox.Add(self.textRead,5, wx.EXPAND | wx.ALL)
            hbox.Layout()
        else:
            self.staticText = wx.StaticText(self, wx.ID_ANY, label="TEST MODE", style=wx.ALIGN_CENTER)
            self.textList = wx.ListBox(self, size=(250, 120))
            hbox.Add(self.textList,5, wx.EXPAND | wx.ALL)
            hbox.Layout()
        
        self.staticText.SetFont(self.font)
        
        self.staticText.CenterOnParent()
        
        self.recordButton =buttons.GenBitmapTextButton(self,1, wx.Bitmap(os.path.join(bitmapDir, "record.png")))
        
        self.pauseButton =buttons.GenBitmapTextButton(self,1, wx.Bitmap(os.path.join(bitmapDir, "stopred.png")))
        
        self.pauseButton.Disable()

        if not self.test_mode:
            self.pauseButton.Hide()
            
        self.timer = wx.Timer(self)
        
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        
        font = wx.Font(40, wx.SWISS, wx.NORMAL, wx.NORMAL, False, u'Comic Sans MS')
        
        self.trackCounter = wx.StaticText(self, label="     00:00",style=wx.EXPAND | wx.ALL)
        
        self.trackCounter.SetFont(font)
        
        self.time = 0
        
        buttonbox.Add(self.recordButton,0, wx.CENTER)
        
        buttonbox.Add(self.pauseButton,0, wx.CENTER)
        
        buttonbox.Add(self.trackCounter,0, flag=wx.CENTER|wx.RIGHT, border=20)
        
        vbox.Add(self.staticText,1, wx.CENTER | wx.ALL, 15)
        
        vbox.Add(hbox,5, wx.EXPAND | wx.ALL, 2)
    
        vbox.Add(buttonbox,1, wx.CENTER| wx.ALL, 2)
        
        self.SetSizer(vbox)
        vbox.Layout()
        
    def OnTimer(self, event):
        """ Manage a GUI timer """
        if self.test_mode:
            self.time = self.time+1
            
        else:
            self.time = self.time-1
            
        secsPlayed = time.strftime('     %M:%S', time.gmtime(self.time))
        wx.CallAfter(Publisher().sendMessage, "update_timer", "   "+secsPlayed)
        #self.trackCounter.SetLabel(secsPlayed)
      
    def toggle_record_button(self):
        """ Enable stop button """
        
        self.pauseButton.Enable()
        self.recordButton.Disable()    
         
        
    def toggle_stop_button(self): 
        """ Enable record button """
        
        self.time = 0
        wx.CallAfter(Publisher().sendMessage, "update_timer", "     00:00")
        self.pauseButton.Disable()
        self.recordButton.Enable()
    
    def set_time_label(self, time):
        t = time.data
        self.trackCounter.SetLabel(t)

            
class Model:
    """ Represents and manages all data model """
    
    def __init__(self, test_mode=None):
        self.voiceid = None
        #self.db = GMMVoiceDB('/home/michela/SpeakerRecognition/voiceid/scripts/test_db/')
        self.db = GMMVoiceDB(os.path.expanduser('~/.voiceid/gmm_db/'))
        #self._cluster = None
        #self._partial_record_time = 5
        self.test_mode = test_mode
        self.queue_processes = []
        self._observers = []
        self._processing_thread = None
        self._queue_thread = []
        self.thrd_n = 2
        self._scores = {}
        self.threshold = -32.160
        
    def attach(self, observer):
        """ Attach a new observer """
        
        if not observer in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        """ Deatach a new observer """
        
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    def notify(self, modifier=None):
        """ Notify an update """
        
        for observer in self._observers:
            if modifier != observer:
                observer.update()

    def save_callback(self, file_=None):
        """ Adds a file to the queue after it's been saved """
        if self.test_mode == True:
            vid = Voiceid(self.db, file_, single = True)
            self.queue_processes.append((vid,None))
            

    def set_speaker_name(self, name, file_):
        """ Adds speaker model in db  """
        shutil.move(file_,name+".wav")
        r = name+".wav"
        f = os.path.splitext(r)[0]
        return self.db.add_model(str(f),name)
        
    def alive_threads(self, t):
        """Check how much threads are running and alive in a thread dictionary
        :param t thread dictionary 
        """ 
        num = 0
        for thr in t:
            if thr.is_alive():
                num += 1
        return num
        
    def on_process(self, conf=1):
        """ Extract speakers from each partial recording file """
        while self.record.is_recording() or self.is_process_running():
            index = 0
            for vid, result in self.queue_processes:
                if result == None:
                   
                    if  self.alive_threads(self._queue_thread)  < self.thrd_n :
                        t = Thread(target=self.extract_speaker, args=(vid,index,conf))
                        self._queue_thread.append(t)
                        self.queue_processes[index] = (vid,['running'])
                        t.start()
                    else :
                        while self.alive_threads(self._queue_thread) >= self.thrd_n:
                            time.sleep(1)  
                        t = Thread(target=self.extract_speaker, args=(vid,index,conf))
                        self._queue_thread.append(t)
                        self.queue_processes[index] = (vid,['running'])
                        t.start()
                index += 1
 
            time.sleep(1)
            
            
            
    def is_process_running(self):
        if len(self.queue_processes) == 0: return True
        for vid, result in self.queue_processes:
                if result == None:
                    return True
        return False
        
    def get_last_result(self):
        """ Return last result """
        p = self.queue_processes[:]
        p.reverse()
        for file_, result in p:
            if result != None and result[0] != "running":
                return result

        print "None last result!!"
        return None
        
    def start_record(self, total_seconds = None, partial_seconds = None, stop_callback=None, save_callback = None, conf = 1):
        """ start a new record process """
        
        self.queue_processes = []
        
        if self.test_mode == True:
            if conf == 1:
                self.record = Record('', total_seconds=total_seconds, partial_seconds = partial_seconds, stop_callback=stop_callback, incremental_mode=True, save_callback=self.save_callback)
            elif conf == 2:
                self.record = Record('', total_seconds=total_seconds, partial_seconds = partial_seconds, stop_callback=stop_callback, incremental_mode=False, save_callback=self.save_callback)
            else:
                self.record = Record('', total_seconds=partial_seconds, partial_seconds = partial_seconds, stop_callback=stop_callback, incremental_mode=False, save_callback=self.save_callback)
        
        else:
            self.record = Record('training',total_seconds, stop_callback=stop_callback,save_callback=save_callback)
            
        self.record.start()
        self._processing_thread = Thread(target=self.on_process, args=(conf,))
        if self.test_mode == True: self._processing_thread.start()
        
    def set_test_mode(self, mode):
        """ Set mode to record - True for test mode False otherwise """
        
        self.test_mode = mode  
        
    def get_test_mode(self):
        """ Return mode to record - True for test mode False otherwise """
        
        return self.test_mode
    
    def stop_record(self):
        """ Stop record process """
        print "stop"
        self.record.stop()
        
    def get_process_status(self):
        if self.test_mode == True:
            q = self.queue_processes[:]
            for file_, result in q:
                if result == None or result[0]=='running':
                    return False
            return True              
                                
    def extract_speaker(self, vid, index, conf):
        """ Extract speaker from a wave """
        vid.extract_speakers(quiet=True, thrd_n=16)
        if conf == 1:
            self.queue_processes[index] = ( vid, vid.get_cluster('S0').get_best_five() )
        elif conf == 2 or conf == 3:
            last_scores = vid.get_cluster('S0').speakers
                
            for i in last_scores:
                if i in self._scores: 
                    self._scores[i] +=  60 +last_scores[i]
                else: self._scores[i] = 60 +last_scores[i]    
                
            
            self.queue_processes[index] = ( vid,sorted(self._scores.iteritems(), key=lambda (k,v): (v,k),
                          reverse=True)[:5])
        
        #print "extract finish",self.queue_processes[index]
        #c= sorted(self._scores.iteritems(), key=lambda (k,v): (v,k),reverse=True)
        #print c
        
        
        self.notify()


class ClusterForm(wx.Dialog):
    def __init__(self, parent, title, label):
        wx.Dialog.__init__(self, parent, 20, title, wx.DefaultPosition, wx.Size(300, 140))
        
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        
        fgs = wx.FlexGridSizer(3, 2, 9, 5)
        
        self.title_tc1 = wx.StaticText(self, label=label)
        
        self.tc1 = wx.TextCtrl(self, size=(150, 25))
        
        self.max = IntCtrl( self, size=(150, 25) )
        
        self.max.Enable( True )
        
        self.max.Hide()
        
        fgs.AddMany([(self.title_tc1), (self.tc1, 1, wx.EXPAND)])
        
        fgs.AddMany([(self.title_tc1), (self.max, 1, wx.EXPAND)])
        
        fgs.AddGrowableRow(2, 1)
        fgs.AddGrowableCol(1, 1)
        
        hbox.Add(fgs, flag=wx.ALL | wx.EXPAND, border=15)
        self.b_ok = wx.Button(self, label='Ok', id=OK_DIALOG)
        self.b_cancel = wx.Button(self, label='Cancel', id=CANCEL_DIALOG)

        buttonbox.Add(self.b_ok, 1, border=15)
        buttonbox.Add(self.b_cancel, 1, border=15)
        
        vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL | wx.EXPAND)
        vbox.Add(buttonbox, flag=wx.ALIGN_CENTER)
        self.SetSizer(vbox)    
class App(wx.App):
    def __init__(self, *args, **kwargs):
        wx.App.__init__(self, *args, **kwargs)
        self.controller = Controller(self)
        
    def OnExit(self):
        pass
       
if __name__ == "__main__":
    app = App(redirect=False)
    app.MainLoop()
