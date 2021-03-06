'''python stuff'''
import sys, time # sys for sys.exit and error info. time for timed connection attempts
from textwrap import wrap # textwrap for text wrapping... mind blown


'''java stuff'''
import os
os.environ['JAVA_HOME'] = '/usr/lib/jvm/java-8-openjdk-amd64' # where java compiler is

from jnius import autoclass # jnius allows java objects to exist and be manipulated in python space
# get android bluetooth classes
BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter') # class representing actual bluetooth antenna and drivers
BTManager = autoclass('lockerapp.BTManager') # custom callback class to respond to bluetooth events
UUID = autoclass('java.util.UUID') # to generate UUID objects from string, see UUID info later on

logd = autoclass('android.util.Log').d # android built-in debugging/logging method
def log(tag, message): # log takes a tag (where in the program the log is from) and a message
    logd("\nlocker-controller." + tag, message+'\n') # adds locker-controller to all tags to identify specific app logs


'''kivy stuff'''
import kivy # kivy is the GUI engine, everything below are kivy-specific objects
kivy.require('1.10.0') # make sure kivy uses right version of objects
# systems
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
# visual stuff
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
# display simple traceback page
# to be used in event of total failure
def error():
    from errorpage import ErrorMain # import errormain from other file
    msg = str(sys.exc_info()) # get error message from sys class
    log("error", msg) # log that error info
    ErrorMain(msg).run() # run a traceback page with that info

# display simple popup with a title, message, and close button
# to be used in simple, nonfatal errors or warnings
def popup(title, message, dismissable=True):
    log("popup", "Showing popup for message: " + message)
    popup = Popup()
    popup.auto_dismiss = dismissable
    popup.size_hint = (None, None)
    popup.title = title

    text = wrap(message, 35)
    text = '\n'.join(text)
    label = Label(text=text, font_size=60)
    label.texture_update()

    pgrid = GridLayout()
    pgrid.rows = 2
    pgrid.cols = 1
    pgrid.add_widget(label)
    pgrid.add_widget(Button(text="Close", on_release=popup.dismiss, size_hint_y=.3))
    popup.size = (1000, label.texture_size[1]+400)
    popup.content = pgrid
    popup.open()

# create ScreenManager for making app navigatable
class ScreenDisplayController(ScreenManager):
    def __init__(self, firstpage, **kwargs):
        super().__init__(**kwargs)
        self.current = firstpage # allow the first shown page to be easily definable

    # method that will govern the app as soon as an attempt to connect to a bluetooth device is made
    def bluetoothBasedDisplayManager(self, ID):
        app = App.get_running_app() # get instance of app class from kivy engine

        log("ScreenDisplayController.bluetoothBasedDisplayManager", "device name passed from handler: " + ID)
        if not self.handleBluetoothID(ID): # if entered bluetooth ID is bad
            log("ScreenDisplayController.bluetoothBasedDisplayManager", "Bad ID entered")
            return # give control back to kivy engine

        log("ScreenDisplayController.bluetoothBasedDisplayManager", "Trying to connect to device.")
        if not app.connectToDevice():
            log("ScreenDisplayController.bluetoothBasedDisplayManager", "Device connection failed.")
            return
        log("ScreenDisplayController.bluetoothBasedDisplayManager", "Connection success")
        self.current = "bt_paired"
    # method to run checks on the user-input bluetooth device name that identifies the locker
    def handleBluetoothID(self, ID):
        app = App.get_running_app() # get instance of app from kivy engine
        app.startBluetoothAdapter() # ensure bluetooth is on

        if ID.replace(" ", "") == "": # make sure user didn't enter just spaces
            log("ScreenDisplayController.handleBluetoothID", "Bluetooth ID blank")
            popup("Bluetooth ID Entry Error", "ID input is blank, please input a name.")

        else: # if Bluetooth id entry has at least some letters
            log("ScreenDisplayController.handleBluetoothID", "Checking paired list for " + ID)
            if app.checkForLocker(ID): # if that name is found among the BT devices paired with the phone
                log("ScreenDisplayController.handleBluetoothID", "Bluetooth ID is on the paired list")
                return True

            else: # if the name is not found on the paired list
                log("ScreenDisplayController.handleBluetoothID", "Bluetooth ID is not on the paired list, displaying message")
                popup("Bluetooth ID Entry Error", "Bluetooth device with ID \"" + ID + "\" is not paired with the phone.")

        return False # return false everywhere it's not true, ie every wrong situation

class MainApp(App):

    # get bluetooth device object. assumes device can use bluetooth, will fail if it cannot!
    bluetooth_adapter = BluetoothAdapter.getDefaultAdapter()

    ''' Bluetooth connection points are defined by UUIDs specified by the manufacturer
        of the device. All of these UUIDs were sourced from one of Adafruit's Bluefruit LE
        information pages:
        https://learn.adafruit.com/getting-started-with-the-nrf8001-bluefruit-le-breakout/adding-app-support
    '''
    uart_service_uuid = UUID.fromString("6E400001-B5A3-F393-E0A9-E50E24DCCA9E") # generic uart
    tx_uuid = UUID.fromString("6E400002-B5A3-F393-E0A9-E50E24DCCA9E") # TX uart
    rx_uuid = UUID.fromString("6E400003-B5A3-F393-E0A9-E50E24DCCA9E") # RX uart

    def send(self, string):
        log("MainApp.send", "Sending string " + string)
        self.btmanager.resetWriteStatus()
        self.btmanager.setTXValue(string)
        self.gatt.writeCharacteristic(self.btmanager.getTX())

        t_end = time.time() + 1.5
        while time.time() < t_end:
            if self.btmanager.messageSentCorrectly():
                log("MainApp.send", "Message send correctly.")
                return

        log("MainApp.send", "Message failed to send.")
        popup("Failed To Communicate With Device", "Tried sending \"" + string + "\" to bluetooth device but failed.")

    def connectToDevice(self):
        self.btmanager = BTManager(self.uart_service_uuid, self.tx_uuid, self.rx_uuid) # create callback object
        gatt = self.device.connectGatt(None, True, self.btmanager) # create bluetooth interactions gatt identifier
        log("MainApp.connectToDevice", "Trying to connect to device.")

        def waitForConnect(wait):
            t_end = time.time() + wait
            while time.time() < t_end: # run this while loop for [wait] seconds
                if self.btmanager.getConnectionState() == 2: # if btmanager connection state equals connected (2)
                    log("MainApp.connectToDevice", "Device connected, waiting 2 seconds for async stuff.")
                    time.sleep(2) # recommended to sleep ~2 seconds after connection for async transactions to finish
                    break # break out of the loop and continue
        def waitForUart(wait):
            t_end = time.time() + wait
            while time.time() < t_end:
                if self.btmanager.getUartStatus():
                    log("MainApp.connectToDevice", "UART discovered and ready.")
                    time.sleep(0.5) # again async transactions but this time shorter is fine.
                    break

        waitForConnect(10) # allow up to 10 sec to connect to BT device
        if self.btmanager.getConnectionState() != 2:
            popup("No Connection Made", "A connection with " + self.device.getName() + " could not be made. Make sure you are close enough and it is powered on.")
            gatt.close()
            return False

        waitForUart(5) # allow up to 5 seconds to check if it is uart compatible
        if not self.btmanager.getUartStatus():
            popup("No UART Ability", "A connection with " + self.device.getName() + " was made but the device does not appear to support Adafruit UART communicatios.")
            gatt.close()
            return False

        self.gatt = gatt
        return True

    def checkForLocker(self, name):
        for device in self.paired_devices:
            if device.getName() == name:
                self.device = device
                log("MainApp.checkForLocker", "Device to be used set to " + str(device))
                return True
        return False

    def startBluetoothAdapter(self):
        # enable bluetooth if not already
        if not self.bluetooth_adapter.isEnabled():
            log("MainApp.startBluetoothAdapter", "Enabling bluetooth adapter")
            self.bluetooth_adapter.enable()
        # wait for state to be STATE_ON, aka ready for use
        while(self.bluetooth_adapter.getState() != 12): # 12 is constant for STATE_ON
            pass # do nothing while it's not ready

    # initialize the bluetooth adapter and update paired_devices property
    def initBluetoothInfo(self):
        self.startBluetoothAdapter() # ensure bluetooth is on

        log("MainApp.getBluetoothInfo", "Getting paired devices")
        self.paired_devices = self.bluetooth_adapter.getBondedDevices().toArray() # get array of paired BT devices

        if not self.paired_devices: # if paired devices is empty
            log("MainApp.getBluetoothInfo", "No paired devices found, failing!")
            return False

        log("MainApp.getBluetoothInfo", "Phone has paired devices")
        return True

    # update paired_devices AND switch screens if necessary (ie no paired devices)
    def getBluetoothInfo(self):
        def correctScreen(name):
            if not self.SDC.current == name:
                self.SDC.current = name # set current screen to param if it's not already

        self.startBluetoothAdapter() # ensure bluetooth is turned on
        # get paired devices from bluetoothadapter
        log("MainApp.getBluetoothInfo", "Getting paired devices")
        self.paired_devices = self.bluetooth_adapter.getBondedDevices().toArray() # get array of paired BT devices

        if not self.paired_devices: # if no devices paired to phone
            correctScreen("no_paired_devices_failure") # switch screen to fail screen
            log("MainApp.getBluetoothInfo", "No paired devices found, failing!")
            return False

        correctScreen("name_entry") # switch screen to proper, non-error screen
        log("MainApp.getBluetoothInfo", "Phone has paired devices")
        return True

    # necessary kivy method that is run when the app is started
    def build(self):
        Builder.load_file('main.kv') # load stylesheet in kvlang

        if not self.initBluetoothInfo(): # if there are no devices paired with the phone
            log("MainApp.build", "Loading first screen no_paired_devices_failure")
            self.SDC = ScreenDisplayController("no_paired_devices_failure") # create screenmanager with failure screen
        else:
            log("MainApp.build", "Loading first screen name_entry")
            self.SDC = ScreenDisplayController("name_entry") # create screenmanager with proper screen

        self.SDC.transition = NoTransition() # the default transition is wonky. Not trying to be pretty, but also not ugly
        return self.SDC # return the screenmanager for kivy engine to pick up and use

# when app is run directly
if __name__ == "__main__":
    # lots of sweeping try/excepts used for easy error finding
    try:
        _app = MainApp() # try instancing the app
    except:
        error() # if it fails show error screen

    # try running the app, this is where it will most likely fail
    try:
        _app.run() # try running the app
    except SystemExit: # if sys.exit is called
        sys.exit() #allow it to finish and quit
    except: # if it fails
        _app.stop() # stop the app
        error() # show error screen
