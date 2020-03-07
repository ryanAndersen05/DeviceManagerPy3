using System.Collections;
using System.Collections.Generic;
using UnityEngine;

using System;
using System.Text;

using System.Threading;

using System.Net;
using System.Net.Sockets;

using System.Runtime.Serialization.Formatters.Binary;
using System.Runtime.Serialization;
using System.IO;

/// <summary>
/// @author Ryan Andersen EQ Games (404-643-1783)
///
/// This is a remade script of the DragonMasterIOManager. This will hopefully improve communication and error handling of devices
/// This class will also be compatible with the newly updated Python3 script
/// </summary>
public class DragonMasterIOManagerPy3 : MonoBehaviour {

    #region static variables
    private static DragonMasterIOManagerPy3 instance;

    public static DragonMasterIOManagerPy3 Instance
    {
        get
        {
            if (instance == null)
            {
                instance = FindObjectOfType<DragonMasterIOManagerPy3>();
            }
            return instance;
        }
    }
    #endregion static variables

    #region enums
    /// <summary>
    /// List of all the buttons that the draxboard can send over
    /// </summary>
    public enum DraxButtonID : ushort
    {
        SHOOT_BUTTON = 0x0001,
        POWER_UP_BUTTON = 0x0002,
        REDEEM_BUTTON = 0x0004,
        MENU_BUTTON = 0x0008,
        ATTENDANT_KEY = 0x0010,//AKA Green Key
        SUPERVISOR_KEY = 0x0020,//AKA Red Key
        CREDIT = 0x0040,//Not sure what button this is correlated to
        DISABLE_MACHINE = 0x0080,//Not really sure what button this is correlated to...
        LOGIC_DOOR = 0x0100,//****CHANGED DOOR INPUTS****
        CASH_DOOR = 0x0200,
        MAIN_DOOR = 0x0400,
    }

    /// <summary>
    /// List of all the output values for our draxboard. The value correlates to the bit that each output is set to
    /// </summary>
    public enum DraxOutput : ushort
    {
        SHOOT_BUTTON_LAMP = 0x0001,
        POWER_UP_BUTTON_LAMP = 0x0002,
        REDEEM_BUTTON_LAMP = 0x0004,
        MENU_BUTTON_LAMP = 0x0008,
        VIBRATOR_MOTOR = 0x0010,
        WIN_LAMP = 0x0020,
        CHANGE_CANDLE_TOP = 0x0040,
        NOT_USED_0 = 0x0080,//This output is not used for anything. May have a value at some point. In which case, please update the name to reflect this
        BELL = 0x0100,
        MACHINE_METER_OUT = 0x0200,
        MACHINE_METER_IN = 0x0400,
        PRINTER_POWER = 0x0800,//BA stands for Bill Acceptor. I know Ian hates acronyms...
        BA_POWER = 0x1000,
        STATION_METER_OUT = 0x2000,
        NOT_USED_1 = 0x4000,
        STATION_METER_IN = 0x8000,
    }

    /// <summary>
    /// Possible States of our Draxboard device
    /// </summary>
    public enum DraxboardState : byte
    {
        Error = 0x00,//At this moment, the only thing we are tracking is whether or not we are disconnected.
        Connected = 0x01,
    }

    /// <summary>
    /// The id for each of our 4 hard meters in our draxboards
    /// </summary>
    public enum HardMeterID
    {
        METER_IN_STATION = 0x00,
        METER_OUT_STATION = 0x01,
        METER_IN_MACHINE = 0x02,
        METER_OUT_MACHINE = 0x03
    }

    /// <summary>
    /// Possible states of our joystick device
    /// </summary>
    public enum JoystickState : byte
    {
        Error = 0x00,
        Connected = 0x01,
    }


    public enum JoystickType : byte
    {
        ULTIMARC_JOYSTICK = 0x01,
        BAOLIAN_JOYSTICK = 0x02
    }

    /// <summary>
    /// List of all possible states that our Bll Acceptor can be in
    /// </summary>
    public enum BillAcceptorState
    {
        ERROR,
        NOT_INIT,//Once a bill acceptor is set to connected make this the default state
        POWER_UP,
        NOTE_STAY,
        IDLE,//Bill Acceptor can accept bills
        INHIBIT,
        UNIT_FAILURE,
        BOX_REMOVED,
        STACKER_JAMMED
    }

    /// <summary>
    /// The avaialbility of our Paper currently remaining in the printer. These values should apply to every type of printer that is added in the future
    /// </summary>
    public enum PaperStatus
    {
        OUT_OF_PAPER = 0x00,
        PAPER_LOW = 0x01,
        PAPER_AVAILABLE = 0x02
    }

    /// <summary>
    /// List of all possible states of our CustomTG02 Printer
    /// </summary>
    public enum CustomPrinterState
    {
        DISCONNECTED,
        ERROR,
        READY,
        PAPER_READY,
        PAPER_JAM,
        PAPER_OBSTRUCTED
    }

    /// <summary>
    /// List of all possible states of our Reliance Printer
    /// </summary>
    public enum ReliancePrinterState : uint
    {
        PRINTER_READY = 0X00,
        COVER_OPEN = 0X01, //The reliance printer's cover is open. Functionality with the printer should stop
        COVER_OPEN2 = 0X02,//Alt cover for reliance printer is open. Fucnctionality with printer should stop
        PAPER_MOTOR_ON = 0X08,
        RS232_ERROR = 0X200,//There was an error with the serial communication. Functionality with printer should stop
        POWER_SUPPLY_VOLTAGE_ERROR = 0X4000,//There is not enough power running to the reiance printer. Fucntionality with printer should stop until this is resolved
        CUTTER_ERROR = 0X10000,//There was an error with the printer cutter. functionality with printer should stop until this is resolved
    }
    #endregion enums

    

    #region const values

    /// <summary>
    /// There is a possible memory leak with threading. Seems that we need to close out of a thread eventually to clear up an resources that are being
    /// used by the method. After we have completed the set number of loops in our thread, we will start a new thread to clear up these resources
    /// </summary>
    public const int MAX_THREAD_READS_BEFORE_STARTING_NEW_THREAD = 500;
    #endregion const values

    #region tcp event values
    //This contains a list of all the events that we can send and receive from our Python application

    //This command will be sent as a single byte event simply to inform python that we are still connected to the our Unity application
    private const byte STATUS_FROM_UNITY = 0x00; //Periodic update that we should receive from Unity to enusre the game is still running. We will close the application if we have not received a message in 60+ seconds
    private const byte DEVICE_CONNECTED = 0x01; //When a new device has successfully been connected to our manager we will send this event to Unity
    private const byte DEVICE_DISCONNECTED = 0x02; //When a new device is successfully removed from our manager we will send this message to Unity
    private const byte OMNI_EVENT = 0x03; //For messages that we send/receive to our omnidongle
    private const byte RETRIEVE_CONNECTED_DEVICES = 0x04; //This will return a device connected event for every currently connected device. This is good on soft reboot when our IO manager does not know what devices are currently connected
    private const byte KILL_APPLICATION_EVENT = 0x05; //This event will trigger an event to kill the main thread, effectively shutting down the entire application

    //DRAX COMMANDS
    private const byte DRAX_ID = 0x10; //The last 4 bits represent the type of device that we are receiving a notification about. In this case the bit 4 represents drax event

    //Send Events
    private const byte DRAX_INPUT_EVENT = 0x11; //For button events that we will send to our Unity App

    //Receive Events
    private const byte DRAX_OUTPUT_EVENT = 0x12; //The short that is passed in using this command is what we will set our drax output state to be
    private const byte DRAX_OUTPUT_BIT_ENABLE_EVENT = 0x13; //Enables the bits that are passed in. Can be multiple bits at once
    private const byte DRAX_OUTPUT_BIT_DISABLE_EVENT = 0x14; //Disables the bits that are passed in. Can be multiple bits at once
    private const byte DRAX_HARD_METER_EVENT = 0X15; //Event to Increment our hard meters taht are attached to our draxboards
    private const byte DRAX_METER_ERROR = 0X16; // This event will be sent regardless of whether or not an error was experienced. The data bit will describe the type of error that we received. Data of 0 means no error was experienced

    //JOYSTICK COMMANDS
    private const byte JOYSTICK_ID = 0X20; // Bit 5 represents joystick id events
    private const byte JOYSTICK_INPUT_EVENT = 0X21; //Input event from the joystick. Sends the x and y values that are currently set on the joystick

    //PRINTER COMMANDS
    private const byte PRINTER_ID = 0X40; //ID to indicate that this is a printer type event

    //Receive Events
    private const byte PRINTER_CASHOUT_TICKET = 0X41; //Command to print a cashout/voucher ticket
    private const byte PRINTER_AUDIT_TICKET = 0X042; //Command to print an audit ticket
    private const byte PRINTER_CODEX_TICKET = 0X43; //Command to print a codex ticket
    private const byte PRINTER_TEST_TICKET = 0X44; //Command to print a test ticket
    private const byte PRINTER_REPRINT_TICKET = 0x45; //Command to print a reprint ticket

    //Send Events
    private const byte PRINT_COMPLETE_EVENT = 0X46; //Upon completing any print job, you should receive a PRINT_COMPLETE_EVENT message to verify that we successfully printed a ticket. This will indicate a scucessful print.
    private const byte PRINT_ERROR_EVENT = 0x47; //If there was an error at some point in the print job, we will send this message instead. This will take the place of a PRINT_COMPLETE_EVENT
    private const byte PRINTER_STATE_EVENT = 0x48; //Returns the state of the printer. 

    //Printer Types
    private const byte CUSTOM_TG02 = 0X01; //
    private const byte RELIANCE_PRINTER = 0X02; //
    private const byte PYRAMID_PRINTER = 0X03; //

    //BILL ACCEPTOR COMMANDS
    private const byte BILL_ACCEPTOR_ID = 0X80; //

    //Send Events
    private const byte BA_BILL_INSERTED_EVENT = 0X81; //Bill was inserted event
    private const byte BA_BILL_ACCEPTED_EVENT = 0X82; //Bill was accepted event
    private const byte BA_BILL_REJECTED_EVENT = 0X83; //Bill was rejected event
    private const byte BA_BILL_RETURNED_EVENT = 0x84; //Bill was returned event
    private const byte BA_BILL_STATE_UPDATE_EVENT = 0x85; //Event to Send the status of the bill acceptor

    //Receive Events
    private const byte BA_ACCEPT_BILL_EVENT = 0X86; //Command to accept the bill that is currently in escrow
    private const byte BA_REJECT_BILL_EVENT = 0X87; //Command to reject the bill that is currently in escrow
    private const byte BA_IDLE_EVENT = 0X88; //Command to set the BA to idle
    private const byte BA_INHIBIT_EVENT = 0X89; //Command to set the BA to inhibit
    private const byte BA_RESET_EVENT = 0X8a; //Command to reset the BA (Good if there is some error that isn't resolved automatically)

    #endregion tcp event values




    #region important variables
    /// <summary>
    /// This will hold a dictionary of all the assigned player Station datas that are currently set. If a key is not found that player station
    /// </summary>
    private Dictionary<uint, PlayerStationData> playerStationDeviceDictionary = new Dictionary<uint, PlayerStationData>();


    /// <summary>
    /// This list is ordered by playerstation index to the associated playerstation hash. A value of 0 for our playerStationHash should be recogonized as unassigned. Any other value will mean that the player station is assigned
    /// 
    /// For example index at 0 will be playerstation 1's playerStation Hash
    /// This list will be populated automatically if the playerstation hash has never been heard from. Either the playerstation index can be set by the hardware
    /// in Drax version 6.1x+ or you can manually set them through the settings menu. The default will be to set them in the order that the hashes are received, which will more than likely not be the correct order for each player station
    /// </summary>
    private PlayerStationData[] playerStationDataOrderList = new PlayerStationData[10];//cChange the value here to support a larger group of player stations. Setting it to 10, since I don't think we go above that in the near future.


    private TCPManager associatedTCPManager;
    #endregion important variables

    #region monobehaviour methods
    private void Awake()
    {
        instance = this;
        StartupDragonMasterIOManagerPy3();
        for (int i = 0; i < playerStationDataOrderList.Length; i++)
        {
            playerStationDataOrderList[i] = new PlayerStationData();
            playerStationDataOrderList[i].playerStationIndex = i;
        }

        LoadPeripheralSettings();
    }

    private void Update()
    {
        associatedTCPManager.PrepareBytesToSendThroughTCP();
        List<byte[]> listOfAllReadEvents = associatedTCPManager.UpdateReadPythonEventsIfValid();
        if (listOfAllReadEvents != null)
        {
            foreach (byte[] eventPacket in listOfAllReadEvents)
            {
                InterpretEventRecievedFromPython(eventPacket);
            }
        }

    }
    /// <summary>
    /// If this value is marked as false, then we will delay the application before shutting down
    /// </summary>
    private bool applicationQuitDelayed = false;
    private bool applicationReadyToQuit = false;

    private void OnApplicationQuit()
    {
        if (!applicationQuitDelayed)
        {
            StartCoroutine(DelayApplicationQuit());
            return;
        }
        if (!applicationReadyToQuit)//If the application has not waited the appropriate amount of time before shutting off we will cancel the application quit event.
        {
            Application.CancelQuit();
            return;
        }
    }

    /// <summary>
    /// This coroutine will delay the act of quitting the game by 3 seconds to give the appropriate amount of time to allow Unity to send a kill event to our python application
    /// 
    /// 3 seconds is honestly kind of excessive. Could probably get away with 1 second or so...
    /// </summary>
    /// <returns></returns>
    private IEnumerator DelayApplicationQuit()
    {
        applicationQuitDelayed = true;

        Application.CancelQuit();
        Time.timeScale = 0;
        SendKillPythonApplicationEvent();
        yield return new WaitForSecondsRealtime(3);

        applicationReadyToQuit = true;

        Application.Quit();
    }

    /// <summary>
    /// sends a status packet to our python application every 5 seconds to let it know that we are still alive. If a minute has passed without receiving
    /// a status message. our python application will run a force shutdown, which should restart the game
    /// </summary>
    /// <returns></returns>
    private IEnumerator PeriodicallySendStatusToOurPythonApplicationToPreventShutdown()
    {
        while (this.enabled)
        {
            SendStatusUpdateToPythonApplication();
            yield return new WaitForSecondsRealtime(.5f);
        }
    }
    #endregion monobehaviour methods

    #region dragon master io manager functions

    /// <summary>
    /// This will assign the correct method based on the packet ID that we received from our Python application.
    /// </summary>
    private void InterpretEventRecievedFromPython(byte[] packetReceivedFromPython)
    {
        
        if (packetReceivedFromPython == null || packetReceivedFromPython.Length == 0)
        {
            Debug.LogWarning("Received an invalid packet to interpret. This shouldn't really happen unless there is an issue with threading");
            return;
        }
        byte eventID = packetReceivedFromPython[0];
        switch (eventID)
        {
            //General Events
            case DEVICE_CONNECTED:
                this.OnDeviceConnectedEvent(packetReceivedFromPython);
                return;
            case DEVICE_DISCONNECTED:
                this.OnDeviceDisconnectedEvent(packetReceivedFromPython);
                return;
            case OMNI_EVENT:
                this.OnOmnidongleEventReceived(packetReceivedFromPython);
                return;

            //Drax Events
            case DRAX_INPUT_EVENT:
                this.OnDraxboardInputEventReceived(packetReceivedFromPython);
                return;
            case DRAX_OUTPUT_EVENT:
                this.OnDraxboardOutputEventReceived(packetReceivedFromPython);
                return;
            case DRAX_METER_ERROR:
                this.OnMeterErrorEventReceived(packetReceivedFromPython);
                return;

            //Joystick Events
            case JOYSTICK_INPUT_EVENT:
                this.OnJoystickAxisEventReceieved(packetReceivedFromPython);
                return;

            //Printer events
            case PRINT_COMPLETE_EVENT:
                this.OnPrintCompletedSuccessfulEvent(packetReceivedFromPython);
                return;
            case PRINT_ERROR_EVENT:
                this.OnPrintCompletedWithErrorEvent(packetReceivedFromPython);
                return;
            case PRINTER_STATE_EVENT:
                this.OnPrinterStateReceived(packetReceivedFromPython);
                return;

            //Bill Acceptor Events
            case BA_BILL_INSERTED_EVENT:
                this.OnBillWasInserted(packetReceivedFromPython);
                return;
            case BA_BILL_ACCEPTED_EVENT:
                this.OnBillWasStacked(packetReceivedFromPython);
                return;
            case BA_BILL_REJECTED_EVENT:
                this.OnBillWasRejected(packetReceivedFromPython);
                return;
            case BA_BILL_RETURNED_EVENT:
                this.OnBillWasReturned(packetReceivedFromPython);
                return;
            case BA_BILL_STATE_UPDATE_EVENT:
                this.OnBillAcceptorStateReceived(packetReceivedFromPython);
                return;
        }
        Debug.LogWarning("EventID: " + eventID.ToString() + " - There was no function assigned to this EventID");
    }

    /// <summary>
    /// Call this method from our Overseer to properly start up our Device Manager.
    /// </summary>
    public void StartupDragonMasterIOManagerPy3()
    {
        this.associatedTCPManager = new TCPManager(this);

        StartCoroutine(PeriodicallySendStatusToOurPythonApplicationToPreventShutdown());
    }


    /// <summary>
    /// This will create a packet that will be queued for ou
    /// </summary>
    /// <param name="eventIDByte"></param>
    /// <param name="packetDatas"></param>
    /// <param name="playerStationHash"></param>
    public void QueueEventToSendToPython(byte eventIDByte, byte[] packetDatas, uint playerStationHash = 0)
    {
        byte[] packetToQueue = new byte[packetDatas.Length + 3];
        packetToQueue[2] = eventIDByte;
        ushort sizeOfPacketToSend = (ushort)(packetDatas.Length + 1);
        byte higherByte = (byte)((sizeOfPacketToSend >> 8) & 0xff);
        byte lowerByte = (byte)(sizeOfPacketToSend & 0xff);
        packetToQueue[0] = higherByte;
        packetToQueue[1] = lowerByte;

        this.associatedTCPManager.QueueEventToSendToPythonApplication(packetToQueue);//Queue our newly created packet in our TCP Manager

    }

    #endregion dragon master io manager functions

    #region general events
    /// <summary>
    /// This method will appropriately assign a device to a player station or device manager if it has not already done so
    /// 
    /// A playerStationHash of 0 will correlate to a general machine device. For example the Omnidongle does not correlate to any specific player station. If there are any other
    /// devices that are added that do not correlate to a specific player station, send it with a station hash of 0
    /// 
    /// 
    /// </summary>
    /// <param name="bytePacket"></param>
    private void OnDeviceConnectedEvent(byte[] bytePacket)
    {

        byte deviceID = bytePacket[5];
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(bytePacket);

        PlayerStationData playerStation;
        switch (deviceID)
        {
            case OMNI_EVENT:
                OmnidongleManager.Instance.OmnidongleDeviceConnected();
                return;

            case DRAX_ID:
                byte playerStationIndex = bytePacket[8];//In later versions of firmware, player station index can be assigned through the draxboard. This will return 0 if the version does not support this feature.
                AddPlayerStationToDeviceDictionaryIfNotAssigned(playerStationHash, (int)playerStationIndex - 1);

                playerStation = GetPlayerStationDataFromPlayerStationHash(playerStationHash);

                if (playerStation == null)
                {
                    Debug.LogError("There was an error connecting the DRAXBOARD.... I don't know how that happened.");
                    return;
                }

                playerStation.draxboardState = DraxboardState.Connected;

                byte draxVersionHigh = bytePacket[6];// Drax version high.low
                byte draxVersionLow = bytePacket[7];
                playerStation.draxVersionHigh = draxVersionHigh;
                playerStation.draxVersionLow = draxVersionLow;
                return;
            case BILL_ACCEPTOR_ID:
                playerStation = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStation == null)
                {
                    Debug.LogError("There was an error connecting the BILL ACCEPTOR. Perhaps there is no draxboard connected to our player station");
                    return;
                }

                playerStation.billAcceptorState = BillAcceptorState.NOT_INIT;
                return;
            case JOYSTICK_ID:
                playerStation = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStation == null)
                {
                    Debug.LogError("There was an error connecting the JOYSTICK. Perhaps there is no draxboard connected to our player station");
                    return;
                }

                playerStation.joystickState = JoystickState.Connected;
                // playerStation.joystickType = (JoystickType)
                return;
            case PRINTER_ID:
                playerStation = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStation == null)
                {
                    Debug.LogError("There was an error connecting the PRINTER. Perhaps there is no draxboard connected to our player station");
                    return;
                }

                playerStation.paperAvailability = PaperStatus.OUT_OF_PAPER;
                playerStation.printerTypeAssignedToStation = CUSTOM_TG02;
                return;
        }
    }

    /// <summary>
    /// This method will appropriately remove a device from a player station or the device manager if it has nto already done so
    /// </summary>
    /// <param name="bytePacket"></param>
    private void OnDeviceDisconnectedEvent(byte[] bytePacket)
    {
        byte deviceID = bytePacket[5];
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(bytePacket);

        PlayerStationData playerStationData;

        switch (deviceID)
        {
            case OMNI_EVENT:
                OmnidongleManager.Instance.OmnidongleDeviceDisconnected();
                return;

            case DRAX_ID:
                playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStationData == null)
                {
                    Debug.LogError("There was an error disconnecting our DRAXBOARD.... I don't know how we got here");
                }
                playerStationData.draxboardState = DraxboardState.Error;
                return;
            case BILL_ACCEPTOR_ID:
                playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStationData == null)
                {
                    Debug.LogError("There was an error disconnecting our BILL ACCEPTOR.... I don't know how we got here");
                }
                return;
            case JOYSTICK_ID:
                playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStationData == null)
                {
                    Debug.LogError("There was an error disconnecting our JOYSTICK.... I don't know how we got here");
                }
                playerStationData.joystickState = JoystickState.Error;
                return;
            case PRINTER_ID:
                playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
                if (playerStationData == null)
                {
                    Debug.LogError("There was an error disconnecting our PRINTER.... I don't know how we got here");
                }
                return;
        }
    }



    /// <summary>
    /// Call this method whenever you want to send a status event to our python application
    /// </summary>
    private void SendStatusUpdateToPythonApplication()
    {
        QueueEventToSendToPython(STATUS_FROM_UNITY, new byte[] { });
    }

    /// <summary>
    /// This is good to call on the start of our application. This will allow us to collect all connected devices on a soft reset. The python appliation does not reset unless the dragon master appliation has been completely turned off.
    /// </summary>
    private void SendRequestAllConnectedDevicesEvent()
    {
        QueueEventToSendToPython(RETRIEVE_CONNECTED_DEVICES, new byte[] { });
    }

    /// <summary>
    /// This is something we should call ONLY if the Dragon Master Application is doing a complete restart. This will kill the Python device manager
    /// application. It should restart on its own due to the bash script. Same will apply to the Unity Application.
    /// </summary>
    private void SendKillPythonApplicationEvent()
    {
        QueueEventToSendToPython(KILL_APPLICATION_EVENT, new byte[] { });
    }
    
    #endregion general events

    #region omnidongle events
    /// <summary>
    /// Sends an encrypted packet to our omnidongle
    /// </summary>
    /// <param name="packetToSend"></param>
    public void SendOmnidonglePacket(byte[] packetToSend)
    {
        QueueEventToSendToPython(OMNI_EVENT, packetToSend);
    }

    /// <summary>
    /// This method should send our encrypted packet to our omnidongle manager to be interpreted
    /// </summary>
    /// <param name="tcpPacketReceived"></param>
    public void OnOmnidongleEventReceived(byte[] tcpPacketReceived)
    {
        byte[] omnidongleReceivedPacket = new byte[tcpPacketReceived.Length - 1];

        for (int i = 0; i < omnidongleReceivedPacket.Length; i++)
        {
            omnidongleReceivedPacket[i] = tcpPacketReceived[i + 1];
        }

        OmnidongleManager.Instance.ReceiveDataFromOmnidongle(omnidongleReceivedPacket);
    }
    #endregion omnidongle events

    #region drax events

    /// <summary>
    /// This method will toggle the input state of the draxobarod based on the bute array packet that is passed in
    /// </summary>
    /// <param name="pakcetEvent"></param>
    private void OnDraxboardInputEventReceived(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);
        if (playerStationHash == 0)
        {
            Debug.LogError("The player station hash of our draxboard input event was 0. Something may have gone wrong");
        }

        PlayerStationData stationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);

        if (stationData == null)
        {
            return;
        }

        ushort inputState = (ushort)(packetEvent[5] << 8);
        inputState += packetEvent[6];

        stationData.DraxInputStateReceived(inputState);//Send the current input state to the player station class to be stored and perform any necessary actions if needed

    }

    /// <summary>
    /// You should receive this method every time the state of the draxboard output is updated
    /// </summary>
    private void OnDraxboardOutputEventReceived(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        if (playerStationHash == 0)
        {
            Debug.LogError("The player station hash of our draxboard output event was 0. Something is very wrong here");
            return;
        }

        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
        if (playerStationData == null)
        {
            return;
        }

        uint draxoutput = (packetEvent[5]);//Drax is stupid and uses little endian. Everything else in our application should use big endian. Make sure to keep that in mind
        draxoutput += (uint)(packetEvent[6] << 8);
        draxoutput += (uint)(packetEvent[7] << 16);
        draxoutput += (uint)(packetEvent[8] << 24);

        playerStationData.draxOutputState = draxoutput;
    }

    /// <summary>
    /// Call this method upon receiving an error for our Draxboard hard meters
    /// </summary>
    /// <param name="plyaerStationHash"></param>
    public void OnMeterErrorEventReceived(byte[] packetEvent)
    {
        Debug.LogWarning("Meter Error Received. No functionality found for this method");
    }

    

    /// <summary>
    /// If you would like to enable one specific bit in our draxboard output, call this method with the output value to toggle on
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <param name="outputToEnable"></param>
    public void SendDraxboardBitEnable(int playerIndexInOverseer, DraxOutput outputToEnable)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndexInOverseer);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There is no playerstation hash assigned to this player index. Perhaps you need to run calibrate");
            return;
        }

        ushort outputEnableShort = (ushort)outputToEnable;
        byte[] outputAsPacket = new byte[2];
        outputAsPacket[0] = (byte)((outputEnableShort >> 8) & 0xff);
        outputAsPacket[1] = (byte)(outputEnableShort & 0xff);

        QueueEventToSendToPython(DRAX_OUTPUT_BIT_ENABLE_EVENT, outputAsPacket, playerStationHash);

    }
    
    /// <summary>
    /// If you would like to disable one specific bit in our draxboard output, call this method with the output value to toggle off
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <param name="outputToDisable"></param>
    public void SendDraxboardBitDisable(int playerIndexInOverseer, DraxOutput outputToDisable)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndexInOverseer);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There is no playerstation hash assigned to this player index. Perhaps you need to run calibrate");
            return;
        }

        ushort outputEnableShort = (ushort)outputToDisable;
        byte[] outputAsPacket = new byte[2];
        outputAsPacket[0] = (byte)((outputEnableShort >> 8) & 0xff);
        outputAsPacket[1] = (byte)(outputEnableShort & 0xff);

        QueueEventToSendToPython(DRAX_OUTPUT_BIT_DISABLE_EVENT, outputAsPacket, playerStationHash);
    }

    

    /// <summary>
    /// Sends an event to tick our hard meters to the desired player station
    /// </summary>
    public void SendTicksToOurHardMeter(int playerIndexInOverseer, ushort numberOfTicksToSend, HardMeterID hardMeterID)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndexInOverseer);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There was no player station hash associated with this Player index. Perhaps you will need to run the calibration screen");
            return;
        }
        byte hardMeterIDByte = (byte)hardMeterID;
        byte hardMeterTicksHigh = (byte)((numberOfTicksToSend >> 8) & 0xff);
        byte hardMeterTickLow = (byte)((numberOfTicksToSend >> 0) & 0xff);

        QueueEventToSendToPython(DRAX_HARD_METER_EVENT, new byte[] { hardMeterIDByte, hardMeterTicksHigh, hardMeterTickLow },  playerStationHash);
    }

    /// <summary>
    /// Returns whether or not a button is currently being held down for the playerstation index that is passed through
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <param name="button"></param>
    /// <returns></returns>
    public bool GetButtonHeld(int playerIndexInOverseer, DraxButtonID button)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndexInOverseer);
        if (playerStationData == null)
        {
            return false;
        }

        ushort buttonIDAsUshort = (ushort)button;

        return (playerStationData.playerStationInputState & buttonIDAsUshort) != 0;
    }

    /// <summary>
    /// Returns true the first frame that this button was registered as held down
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <param name="button"></param>
    /// <returns></returns>
    public bool GetButtonDown(int playerIndexInOverseer, DraxButtonID button)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndexInOverseer);
        if (playerStationData == null)
        {
            return false;
        }

        ushort buttonIDAsUshort = (ushort)button;

        return (buttonIDAsUshort & playerStationData.playerStationInputStatePressed) != 0;
    }

    /// <summary>
    /// Returns true the first frame that this button was registered as released.
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <param name="button"></param>
    /// <returns></returns>
    public bool GetButtonUp(int playerIndexInOverseer, DraxButtonID button)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndexInOverseer);
        if (playerStationData == null)
        {
            return false;
        }

        ushort buttonIDAsUshort = (ushort)button;

        return (buttonIDAsUshort & playerStationData.playerStationInputStateReleased) != 0;
    }

    /// <summary>
    /// Returns a player station has if someone just pressed the button. Returns the first player station based on its hash in the dictionary if there are multiple stations that pressed the button at the same time
    /// </summary>
    /// <returns></returns>
    public uint GetButtonDownAny(DraxButtonID buttonID)
    {
        ushort buttonUshort = (ushort)buttonID;
        foreach (PlayerStationData stationData in playerStationDeviceDictionary.Values)
        {
            if ((stationData.playerStationInputStatePressed & buttonUshort) != 0)
            {
                return stationData.playerStationHash;
            }
        }
        return 0;
    }

    /// <summary>
    /// Returns a player station hash if someone just released the button. Returns the first player station based on its hash in the dictionary if there are multiple stations that pressed the button at the same time
    /// </summary>
    /// <param name="buttonID"></param>
    /// <returns></returns>
    public uint GetButtonUpAny(DraxButtonID buttonID)
    {
        ushort buttonUshort = (ushort)buttonID;
        foreach(PlayerStationData stationData in playerStationDeviceDictionary.Values)
        {
            if ((stationData.playerStationInputStateReleased & buttonUshort) != 0)
            {
                return stationData.playerStationHash;
            }
        }

        return 0;
    }
    #endregion drax events

    #region joystick events
    /// <summary>
    /// This will set the state of the joystick axes based on the packet that is passed in
    /// </summary>
    /// <param name="packetEvent"></param>
    public void OnJoystickAxisEventReceieved(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);
        if (playerStationHash == 0)
        {
            Debug.LogError("Our joystick event had a player station hash of 0. Perhaps something went wrong with the connected Draxboard");
            return;
        }

        PlayerStationData stationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
        if (stationData == null)
        {
            // Debug.LogWarning("The joystick data that was passed in did not have a playerstation hash associated with it. This event will be skipped");
            return;
        }

        stationData.SetFromRawJoystickValues(packetEvent[5], packetEvent[6]);
    }


    public void SetJoystickAxesSwapped(int playerIndex, bool SwapJoystickAxisValues)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndex);
        
        if (playerStationData != null)
        {
            playerStationData.swapAxisValues = SwapJoystickAxisValues;
        }
    }

    /// Returns whether or not our joystick axes are set to be swapped.
    /// NOTE: This does not require a joystick to be connected to return a value
    public bool GetJoystickAxesSwapped(int playerIndex) 
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndex);

        if (playerStationData != null)
        {
            return playerStationData.swapAxisValues;
        }

        return false;
    }

    /// <summary>
    /// Returns the adjusted y-axis value for the joystick assigned to the player index that is passed through
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <returns></returns>
    public float GetVerticalJoystickAxis(int playerIndexInOverseer)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndexInOverseer);
        if (playerStationData == null)
        {
            return 0;
        }

        return AdjustJoystickAxisNormalized(playerStationData.joystick_yAxis);
    }

    /// <summary>
    /// Returns the adjusted x-axis value for the joystick assigned to the player index that is passed through
    /// </summary>
    /// <param name="playerIndexInOverseer"></param>
    /// <returns></returns>
    public float GetHorizontalJoystickAxis(int playerIndexInOverseer)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerIndexInOverseer);
        if (playerStationData == null)
        {
            return 0;
        }

        return AdjustJoystickAxisNormalized(playerStationData.joystick_xAxis);
    }

    /// <summary>
    /// Returns a value betweeen -1 and 1 that is a collection of all the joysticks added together.
    /// </summary>
    /// <returns></returns>
    public float GetAllJoytickHorizontal()
    {
        float horizontalTotal = 0;
        for (int i = 0; i < playerStationDataOrderList.Length; i++)
        {
            horizontalTotal += GetHorizontalJoystickAxis(i);
        }
        return Mathf.Min(Mathf.Max(-1, horizontalTotal), 1);
    }

    /// <summary>
    /// Returns a value between -1 and 1 that is a collection of all the joysticks added together.
    /// </summary>
    /// <returns></returns>
    public float GetAllJoystickVertical()
    {
        float verticalTotal = 0;
        for (int i = 0; i < playerStationDataOrderList.Length; i++)
        {
            verticalTotal += GetVerticalJoystickAxis(i);
        }
        return Mathf.Min(Mathf.Max(-1, verticalTotal), 1);
    }
    /// <summary>
    /// Normalizes a joystick byte value that we receive from our python application to a normalized value that we
    /// can use in our Unity Application
    /// </summary>
    /// <param name="joystickAxisValue"></param>
    /// <returns></returns>
    private float AdjustJoystickAxisNormalized(byte joystickAxisValue)
    {
        
        float adjustedJoystickValue = joystickAxisValue;
        adjustedJoystickValue -= PlayerStationData.JOYSTICK_AXIS_OFFSET;
        adjustedJoystickValue /= PlayerStationData.JOYSTICK_AXIS_OFFSET;

        return adjustedJoystickValue;
    }
    #endregion joystick events

    #region bill acceptor events
    /// A bill was inserted and is now waiting approval to stack it. Either the user will stack it or it will be automatically accepted or rejected upon
    /// receiving a bill based on certain condtions
    public void OnBillWasInserted(byte[] packetEvent) 
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        if (playerStationHash == 0)
        {
            return;
        }

        int playerStationIndex = GetPlayerStationIndexFromPlayerStationHash(playerStationHash);


    }

    /// If a bill was stacked that means that we have completed the acceptance process of our bill and can now add credits to the player that is associated with this index
    public void OnBillWasStacked(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        if (playerStationHash == 0)
        {
            return;
        }

        int playerStationIndex = GetPlayerStationIndexFromPlayerStationHash(playerStationHash);
    }

    /// This method will be called whe we retrieve a command to says that we have successfully rejected a bill
    public void OnBillWasRejected(byte[] packetEvent)
    {
        uint plyaerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        if (plyaerStationHash == 0)
        {
            return;
        }

        int playerStationIndex = GetPlayerStationIndexFromPlayerStationHash(playerStationHash);
    }

    /// This method will be called upon a bill being returned from the bill acceptor
    /// Thsi will carry out no action in the game, but should log the fact that we did receive a bill
    public void OnBillWasReturned(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        if (playerStationHash == 0)
        {
            return;
        }

        int playerStationIndex = GetPlayerStationIndexFromPlayerStationHash(playerStationHash);
    }

    //Every time the state is updated in the bill acceptor, this method should be called. We can also get this, but requesting the state manually
    public void OnBillAcceptorStateReceived(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        if (playerStationHash == 0)
        {
            return;
        }

        int playerStationIndex = GetPlayerStationIndexFromPlayerStationHash(playerStationHash);

    }

    // Sends a command to the associated bill acceptor to accept the bill that is currently being held in escrow
    public void AcceptBillThatIsCurrentlyInEscrow(int playerIndex) 
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There was no player station hash associated with the player index. Perhaps you will need to calibrate the player stations");
            return;
        }
        QueueEventToSendToPython(BA_ACCEPT_BILL_EVENT, new byte[] { }, playerStationHash);
    }

    //Sends a command to the associated bill acceptor to reject the bill that is curernetly being held in escrow
    public void RejectBillThatIsCurrentlyInEscrow(int playerIndex) 
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There was no player station hash associated with the player index. Perhaps you will need to calibrate the player stations");
            return;
        }

        QueueEventToSendToPython(BA_REJECT_BILL_EVENT, new byte[] {}, playerStationHash);
    }

    //Sets the bill acceptor that is associated with the player index to idle
    public void SendSetBillAcceptorToIdle(int playerIndex)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There was no player station hash associated with the player index. Perhaps you will need to calibrate the player stations");
            return;
        }

        QueueEventToSendToPython(BA_IDLE_EVENT, new byte[] { }, playerStationHash);
    }

    //Set the bill acceptor that is associated with the player index to inhibit
    public void SendSetBillAcceptorToInhibit(int playerIndex)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There was no player station hash associated with player index. Perhaps you need to calibrate the player stations");
            return;
        }

        QueueEventToSendToPython(BA_INHIBIT_EVENT, new byte[] { }, playerStationHash);
    }

    //Sends a command to our bill acceptors to run a reset to the associated player station
    public void SendResetCommandToBillAcceptor(int playerIndex)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0) 
        {
            Debug.LogWarning("There was no player station hash associated with the player index. Perhaps you will need to calibrate the player stations");
            return;
        }
        
        QueueEventToSendToPython(BA_RESET_EVENT, new byte[]{ }, playerStationHash);
    }

    //This will send a command to retrieve the state of the bill acceptor that is associated with the player station index that is passed in
    public void RequestBillAcceptorState(int playerIndex)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There is no player station associated with this ");
            return;
        }
        
        QueueEventToSendToPython(BA_BILL_STATE_UPDATE_EVENT, new byte[] {}, playerStationHash);
    }
    #endregion bill acceptor events

    #region printer events
    //Blocks all print events until the previous one has been completed. An operator will also have the ability to manually
    //clear the printer error to allow for another attempt at printing if it gets locked ups
    private void BeginCoroutineToBlockPrintUntilPrintJobVerificationReturned(uint playerStationHash) 
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);

        if (playerStationData != null)
        {
            StartCoroutine(playerStationData.PrintSentWaitingForResponse());
        }
    }

    /// <summary>
    /// This method will be called upon completing the printing proces of any of our tickets without any error
    /// </summary>
    /// <param name="packetEvent"></param>
    public void OnPrintCompletedSuccessfulEvent(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);
        PlayerStationData pStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);

        if (pStationData == null)
        {
            return;
        }

        pStationData.printJobQueued = false;

    }

    /// <summary>
    /// This method will be called if there is an error during the printing process of any of our tickets
    /// </summary>
    /// <param name="packetEvent"></param>
    public void OnPrintCompletedWithErrorEvent(byte[] packetEvent)
    {
        uint playerStationHash = GetPlayerStationHashFromBytePacketEvent(packetEvent);

        PlayerStationData pStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
        if (pStationData == null)
        {
            return;
        }

        byte printJobType = packetEvent[4];
        switch (printJobType)
        {
            case PRINTER_CASHOUT_TICKET:

                break;
            case PRINTER_REPRINT_TICKET:

                break;
            case PRINTER_TEST_TICKET:

                break;
            case PRINTER_AUDIT_TICKET:

                break;
            case PRINTER_CODEX_TICKET:

                break;
        }
        pStationData.printJobQueued = false;
    }

    //This method should be called upon receiving an event for our printer's state
    //This will update the state that is set in the player station with the hash that is associated with it
    public void OnPrinterStateReceived(byte[] pakcetEvent)
    {

    }


    /// <summary>
    /// Prints a voucher ticket to the playerstation index that is passed through
    /// </summary>
    /// <param name="playerStationIndexToPrintTo"></param>
    public bool PrintVoucherTicket(int playerStationIndexToPrintTo, string creditsToCashout, string validationNumber, DateTime dateTimeOfPrint)
    {
        
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerStationIndexToPrintTo);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("No playerStationHash attched to player station " + playerStationIndexToPrintTo + ". You may need to open the calibration screen");
            return false;
        }

        
        if (GetPrintJobQueuedByPlayerIndex(playerStationIndexToPrintTo))
        {
            Debug.LogWarning("Cannot Print Voucher Ticket At This Moment. Previous Print Job Has Not Completed.");
            return false;
        }

        string printerDataString = "";
        printerDataString = creditsToCashout;
        printerDataString += "|" + (playerStationIndexToPrintTo + 1).ToString();
        printerDataString += "|" + validationNumber;
        printerDataString += "|" + dateTimeOfPrint.Year;
        printerDataString += "|" + dateTimeOfPrint.Month;
        printerDataString += "|" + dateTimeOfPrint.Day;
        printerDataString += "|" + dateTimeOfPrint.Hour;
        printerDataString += "|" + dateTimeOfPrint.Minute;
        printerDataString += "|" + dateTimeOfPrint.Second;

        QueueEventToSendToPython(PRINTER_CASHOUT_TICKET, Encoding.ASCII.GetBytes(printerDataString), playerStationHash);//Converting our printer data to bytes. We want the text in Dragon's Ascent to match what is printed in our python application
        BeginCoroutineToBlockPrintUntilPrintJobVerificationReturned(playerStationHash);

        return true;
    }

    /// <summary>
    /// Sends an event to our python appliation to print out a test ticket. This is primarily to ensure that our printers are properly connected and functioning correctly
    /// </summary>
    /// <param name="playerStationIndex"></param>
    public bool PrintTestticket(int playerStationIndex)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerStationIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("No playerStationHash attched to player station " + playerStationIndex + ". You may need to open the calibration screen");
            return false;
        }

        if (GetPrintJobQueuedByPlayerIndex(playerStationIndex))
        {
            Debug.LogWarning("Cannot Print Test Ticket At This Moment. Previous Print Job Has Not Completed.");
            return false;
        }

        DateTime dateTimeOfPrint = DateTime.Now;

        string testTicketDataString = "";

        testTicketDataString += "|" + dateTimeOfPrint.Year;
        testTicketDataString += "|" + dateTimeOfPrint.Month;
        testTicketDataString += "|" + dateTimeOfPrint.Day;
        testTicketDataString += "|" + dateTimeOfPrint.Hour;
        testTicketDataString += "|" + dateTimeOfPrint.Minute;
        testTicketDataString += "|" + dateTimeOfPrint.Second;

        QueueEventToSendToPython(PRINTER_TEST_TICKET, Encoding.ASCII.GetBytes(testTicketDataString), playerStationHash);

        BeginCoroutineToBlockPrintUntilPrintJobVerificationReturned(playerStationHash);
        return true;
    }

    /// <summary>
    /// Sends an event to our python application to print a reprint ticket. This will use the date and time of the original print job.
    /// </summary>()
    /// <param name="playerStationIndex"></param>
    public bool PrintReprintTicket(int playerStationIndex, string creditsToCashout, string validationNumber, DateTime dateTimeOfOriginalPrint)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerStationIndex);

        if (playerStationHash == 0)
        {
            Debug.LogWarning("No playerStationHash attched to player station " + playerStationIndex + ". You may need to open the calibration screen");
            return false;
        }

        if (GetPrintJobQueuedByPlayerIndex(playerStationIndex))
        {
            Debug.LogWarning("Cannot Print Reprint Ticket At This Moment. Previous Print Job Has Not Completed.");
            return false;
        }

        string reprintDataString = creditsToCashout;
        reprintDataString += "|" + (playerStationIndex + 1).ToString();
        reprintDataString += "|" + validationNumber;
        reprintDataString += "|" + dateTimeOfOriginalPrint.Year;
        reprintDataString += "|" + dateTimeOfOriginalPrint.Month;
        reprintDataString += "|" + dateTimeOfOriginalPrint.Day;
        reprintDataString += "|" + dateTimeOfOriginalPrint.Hour;
        reprintDataString += "|" + dateTimeOfOriginalPrint.Minute;
        reprintDataString += "|" + dateTimeOfOriginalPrint.Second;


        QueueEventToSendToPython(PRINTER_REPRINT_TICKET, Encoding.ASCII.GetBytes(reprintDataString), playerStationHash);

        BeginCoroutineToBlockPrintUntilPrintJobVerificationReturned(playerStationHash);

        return true;
    }

    /// <summary>
    /// Prints a codex ticket to the playerstation index that is passed through
    /// Returns true if we were able to send a code exchange print ticket request
    /// </summary>
    /// <param name="playerStationIndexToPrintTo"></param>
    public bool PrintCodeExchangeTicket(int playerStationIndexToPrintTo, string codexTicketDataString)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerStationIndexToPrintTo);

        if (playerStationHash == 0)
        {
            Debug.LogWarning("No playerStationHash attched to player station " + playerStationIndexToPrintTo + ". You may need to open the calibration screen");
            return false;;
        }

        if (GetPrintJobQueuedByPlayerIndex(playerStationIndexToPrintTo))
        {
            Debug.LogWarning("Cannot Print Codex Ticket At This Moment. Previous Print Job Has Not Completed.");
            return false;
        }

        QueueEventToSendToPython(PRINTER_CODEX_TICKET, Encoding.ASCII.GetBytes(codexTicketDataString), playerStationHash);

        BeginCoroutineToBlockPrintUntilPrintJobVerificationReturned(playerStationHash);
        return true;
    }

    /// <summary>
    /// Call this method to print an audit ticket to our 
    /// Returns true if we were able to send a print audit ticket request to our python application. False if we did not send a request
    /// 
    /// NOTE: This does not block sending a print command to our player station beyond checking if there is a valid printer to send our command to. If you
    /// need to block printing for a reason in-game, be sure to block it from a different location
    /// </summary>
    public bool PrintAuditTicket(int playerStationIndexToPrintTo, string auditTicketDataString)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerStationIndexToPrintTo);

        if (playerStationHash == 0)
        {
            Debug.LogWarning("No playerStationHash attched to player station " + playerStationIndexToPrintTo + ". You may need to open the calibration screen");
            return false;
        }

        if (GetPrintJobQueuedByPlayerIndex(playerStationIndexToPrintTo))
        {
            Debug.LogWarning("Cannot Print Audit Ticket At This Moment. Previous Print Job Has Not Completed.");
            return false;
        }

        QueueEventToSendToPython(PRINTER_AUDIT_TICKET, Encoding.ASCII.GetBytes(auditTicketDataString), playerStationHash);

        BeginCoroutineToBlockPrintUntilPrintJobVerificationReturned(playerStationHash);
        return true;
    }

    /// <summary>
    /// Returns a bool that details whether or not we have a print job queued for the player station index that was passed in to our function
    /// </summary>
    public bool GetPrintJobQueuedByPlayerIndex(int playerStationIndex)
    {
        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationIndexInOverseer(playerStationIndex);
        if (playerStationData == null)
        {
            return false;
        }
        return playerStationData.printJobQueued;
    }

    /// <summary>
    /// Sends a request for the printer that is associated with the player index
    /// </summary>
    public void RequestPrinterState(int playerIndex)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerIndex);
        if (playerStationHash == 0)
        {
            Debug.LogWarning("There was not player station hash associated with this index. Perhaps you will need to run the calibration process");
            return;
        }

        QueueEventToSendToPython(PRINTER_STATE_EVENT, new byte[]{ }, playerStationHash);
    }
    #endregion printer events

    #region player station helper functions
    /// <summary>
    /// This will assing a player station hash to a PlayerIndex. If there was a player station assigned there previously and it does not match the current player station that is being assigned
    /// it will swap the index of both stations
    /// </summary>
    /// <param name="playerStationHashList"></param>
    public void AssignPlayerStationHashToPlayerStationIndex(uint playerStationHash, int playerStationIndexToAssign)
    {
        if (playerStationHash == 0)
        {
            Debug.LogError("You can not assign a playerStationHash of 0...");
            return;
        }

        if (playerStationIndexToAssign >= playerStationDataOrderList.Length || playerStationIndexToAssign < 0)
        {
            Debug.LogError("Value: " + playerStationIndexToAssign + " - The playerStationIndex that you are trying to assign is out of range of our max supported player size.");
            Debug.LogError("Please use a value between 0 and " + playerStationDataOrderList.Length.ToString());
            return;
        }

        if (playerStationDataOrderList[playerStationIndexToAssign].playerStationHash == playerStationHash)
        {
            //This player station is already correctly assigned. No need to carry out this function
            return;
        }

        AddPlayerStationToDeviceDictionaryIfNotAssigned(playerStationHash, playerStationDataOrderList[playerStationIndexToAssign]);

        PlayerStationData playerStationData = GetPlayerStationDataFromPlayerStationHash(playerStationHash);
        playerStationData.playerStationHash = playerStationHash;
    }

    /// This will check if the player station index that is passed in is a valid index to assign. Meaning that there is no valid player station hash already
    /// assigned, the player station index is valid, and the player station hash is valid as well. If all those conditions are met we will assign this
    /// player station hash to the associated player station index

    /// NOTE: If you want to force an assign, you should use 'AssignPlayerStationHashToPlayerStationIndex'
    private void AddPlayerStationToDeviceDictionaryIfNotAssigned(uint playerStationHash, int playerStationIndex)
    {
        if (playerStationHash == 0)
        {
            return;
        }
        if (playerStationIndex < 0 || playerStationIndex >= playerStationDataOrderList.Length)
        {
            return;
        }

        if (playerStationDataOrderList[playerStationIndex].playerStationHash == 0)
        {
            return;
        }
        else 
        {
            AddPlayerStationToDeviceDictionaryIfNotAssigned(playerStationHash, playerStationDataOrderList[playerStationIndex]);
        }
    }

    /// <summary>
    /// Assigne a new player station data to our device dictionary if there is not one. This will return the player station that is associated with that player station hash
    /// </summary>
    /// <param name="playerStationHash"></param>
    /// <returns></returns>
    private void AddPlayerStationToDeviceDictionaryIfNotAssigned(uint playerStationHash, PlayerStationData associatedPlayerStationData)
    {
        if (playerStationHash == 0)
        {
            Debug.LogWarning("A player station hash of 0 was passed in. This value is invalid. Must be greater than 0.");
            return;
        }
        
        if (!playerStationDeviceDictionary.ContainsKey(playerStationHash))
        {
            playerStationDeviceDictionary.Add(playerStationHash, null);
        }

        playerStationDeviceDictionary[playerStationHash] = associatedPlayerStationData;
    }

    /// <summary>
    /// Returns the player station hash for the associted packet event. Be sure that the packet supports a player station hash before using this method.
    /// May return a random hash if not. 
    /// 
    /// Events that are tied to a specific player station, such as the drax Input Event can use this method appropriately
    /// </summary>
    /// <returns></returns>
    public uint GetPlayerStationHashFromBytePacketEvent(byte[] packetEvent)
    {
        uint playerStationHash = 0;
        int numberOfBytesForPlayerStationHash = 4;

        if  (packetEvent == null || packetEvent.Length < (numberOfBytesForPlayerStationHash + 1))
        {
            return 0;//0 is an invalid player station hash. This should never be the 
        }

        for (int i = 0; i < numberOfBytesForPlayerStationHash; i++)
        {
            playerStationHash += (uint)(packetEvent[1 + i] << (8 * (numberOfBytesForPlayerStationHash - 1 - i)));
        }

        return playerStationHash;
    }


    /// <summary>
    /// Returns the player station index based on the hash that was passed through. If the value is negative, the hash that was passed in was invalid
    /// 
    /// Not sure what I would used this for as there is a method to get the player station data object from the playerstationhash which is much more useful in general
    /// </summary>
    /// <returns></returns>
    private int GetPlayerStationIndexFromPlayerStationHash(uint playerStationHash)
    {
        if (playerStationHash == 0)
        {
            return -1;
        }

        for (int i = 0; i < playerStationDataOrderList.Length; i++)
        {
            if (playerStationHash == playerStationDataOrderList[i].playerStationHash)
                return i;
        }

        return -1;
    }

    /// <summary>
    /// Returns a playerstation hash if there is one that is associated with the index that was passed through
    /// 
    /// If 0 is returned the hash is invalid. No hash should have a value of 0
    /// </summary>
    /// <returns></returns>
    private uint GetPlayerStationHashFromPlayerStationIndex(int playerStationIndex)
    {
        if (playerStationIndex < 0 || playerStationIndex >= playerStationDataOrderList.Length)
        {
            return 0;
        }

        return playerStationDataOrderList[playerStationIndex].playerStationHash;
    }


    /// <summary>
    /// Returns the PlayerStationData object that is associated with the playerIndex that is passed in. This will return null if there is no PlayerStationData
    /// associated with that player index
    /// 
    /// </summary>
    /// <param name="playerStationIndexInOverseer"></param>
    /// <returns></returns>
    private PlayerStationData GetPlayerStationDataFromPlayerStationIndexInOverseer(int playerStationIndexInOverseer)
    {
        uint playerStationHash = GetPlayerStationHashFromPlayerStationIndex(playerStationIndexInOverseer);

        if (playerStationHash == 0)
        {
            return null;
        }

        PlayerStationData pStationData = playerStationDeviceDictionary[playerStationHash];
        return pStationData;
    }

    /// <summary>
    /// Returns the PlayerStationData object that is associated with the player station hash that is passed in.
    /// This will return null if there is no PlayerStationData associated with the player station hash that is passed in.
    /// 
    /// Since events will be identified by their player station hash, this method is primarily useful for getting the player station when receiving events from python
    /// </summary>
    /// <param name="playerStationHash"></param>
    /// <returns></returns>
    private PlayerStationData GetPlayerStationDataFromPlayerStationHash(uint playerStationHash)
    {
        if (!playerStationDeviceDictionary.ContainsKey(playerStationHash))
        {
            return null;
        }

        return playerStationDeviceDictionary[playerStationHash];
    }
    #endregion player station helper functions

    #region Player Station Management Classes

    /// <summary>
    /// This class holds all the data related to each individual player station.
    /// There are 4 devices that each player station should have. These include:
    /// 
    /// -Draxboard - Hub for all other devices. Sends input data from the player as well as receives output data from our application to toggle certain functionality (i.e. lights turning on and off, vibrators, power to devices, etc...)
    /// -Joystick - Simply used for axis inputs from the player
    /// -Bill Acceptor - Handles the transaction of paper currency that is inserted by the player. 
    /// -Printer - Prints a voucher ticket for the player and prints other tickets that contain information about the machine for our operator
    /// </summary>
    private class PlayerStationData
    {
        #region const values
        public const byte JOYSTICK_AXIS_OFFSET = 128;
        #endregion const values

        #region drax variables
        public int playerStationIndex
        {
            get 
            {
                return persistedValues.PlayerStationIndex;
            }
            set 
            {
                persistedValues.PlayerStationIndex = value;
            }
        }

        /// <summary>
        /// This is a value that is set by our python application that is derived from the usb path to the device. This will be how we will
        /// identify the player stations between python and our Unity application
        /// </summary>
        public uint playerStationHash 
        {
            get     
            {
                return persistedValues.PlayerStationHash;
            }
            set 
            {
                persistedValues.PlayerStationHash = value;
            }
        }
        
        /// <summary>
        /// The current output state of our draxboard
        /// </summary>
        public uint draxOutputState;

        /// <summary>
        /// This value represents the input state of the player station. If there are no buttons currently being pressed this should display as 0
        /// </summary>
        public ushort playerStationInputState;

        /// <summary>
        /// This value reveals the buttons that were pressed this frame. Each bit correlates to a different button. The bit will be toggled back to 0 once the frame has completed
        /// </summary>
        public ushort playerStationInputStatePressed;

        /// <summary>
        /// This value reveals the buttons that were released this frame. Each bit correlates to a different button. The bit will be toggled back to 0 once the frame has completed
        /// </summary>
        public ushort playerStationInputStateReleased;

        /// <summary>
        /// The current state of our draxboard
        /// </summary>
        public DraxboardState draxboardState;

        /// <summary>
        /// format for the draxboard version number will be draxVersionHigh.draxVersionLow
        /// So if our draxboard is v6.14 for example, draxVersionHigh will equal 6 and draxVersionLow will equal 14
        /// </summary>
        public byte draxVersionHigh;
        public byte draxVersionLow;
        #endregion drax variables

        #region joystick variables
        /// <summary>
        /// If this value is set to true, this will make it so that the y-axis is the horizontal axis and
        /// x-axis will be the vertical. This is used in case our joystick was built inverted, which may be necessary due to space that is 
        /// availble on our Draxboards
        /// </summary>
        public bool swapAxisValues 
        {
            get
            {
                return persistedValues.SwapJoystickAxisValues;
            }
            set 
            {
                persistedValues.SwapJoystickAxisValues = value;
            }
        }

        /// This refers to the type of joystick that is currently plugged into the machine. At the moement we have two types of joystick that we support
        public JoystickType joystickType;

        /// <summary>
        /// Raw x axis from our python application. Any flipping or altering will have to be done in our Axes getter method
        /// </summary>
        public byte joystick_xAxis {get; private set;}

        /// <summary>
        /// Raw y axis from our python application. Any flipping or altering will have to be done in our Axes getter method
        /// </summary>
        public byte joystick_yAxis {get; private set;}

        /// <summary>
        /// The current state of our joystick... until we go more in depth with collecting status from our joystick this will only set it to either connected or disconnected
        /// </summary>
        public JoystickState joystickState;
        #endregion joystick variables

        #region bill acceptor variables
        /// This is a byte code that represents the type of bill acceptor that we are using.
        /// This will just be the order in which we support a new BA. For example 1 represents DBV-400 as that was the first bill acceptor that we supported
        /// A value of 0 means that no bill acceptor type has been set.
        public byte billAcceptorType = 0;

        /// <summary>
        /// The current state of our bill acceptor
        /// </summary>
        public BillAcceptorState billAcceptorState;

        /// The version of the bill acceptor that we are using. This is sent as a string from our bill acceptor and we pass along those ascii bytes from our python application
        public string billAcceptorVersion;

        #endregion bill acceptor variables

        #region printer variablesS
        /// <summary>
        /// Whenever we send a print job to our python application, we should mark this variable as true until we have received a response from python that the print job has completed
        /// 
        /// Can be a response as an error or a success. As long as we receive something. Potentially may want to add a timeout of some sort that will allow players to attempt again, but an operator should get involved at this point
        /// </summary>
        public bool printJobQueued;

        /// <summary>
        /// Due to the fact that different printers behave differently and send different status messages, it is important that we know the printer type that we are using 
        /// per player station
        /// </summary>
        public byte printerTypeAssignedToStation;

        /// <summary>
        /// The state of the printer, specific to custom printers
        /// </summary>
        public CustomPrinterState customPrinterState;
        /// <summary>
        /// The State of our printer specific to our Reliance Printer. This will have different states compared to other devices
        /// </summary>
        public ReliancePrinterState reliancePrinterState;

        /// <summary>
        /// This is a container that will hold values that should be persisted among play sessions
        /// </summary>
        public PersistedPlayerStationValues persistedValues {get; private set; }

        /// <summary>
        /// Shows how much paper is available in our printer
        /// </summary>
        public PaperStatus paperAvailability;
        #endregion printer variables

        #region initializer
        /// <summary> 
        /// Use this when a new player station 
        /// </summary>
        public PlayerStationData()
        {
            persistedValues = new PersistedPlayerStationValues();
        }

        /// <summary> 
        /// Use this overload method when reloading player station information on startup.
        /// </summary>
        public PlayerStationData(PersistedPlayerStationValues persistedValues)
        {
            this.persistedValues = persistedValues;
        }
        #endregion initializer

        #region draxboard events
        /// <summary>
        /// Call this method whenever we have received an input event from our Draxboard
        /// </summary>
        /// <param name="inputEvent"></param>
        public void DraxInputStateReceived(ushort inputState)
        {
            ushort deltaInputstate = (ushort)(this.playerStationInputState ^ inputState);
            this.playerStationInputState = inputState;

            var bitArray = new System.Collections.BitArray (System.BitConverter.GetBytes(deltaInputstate));
            
            for (int i = 0; i < bitArray.Length; i++)
            {
                if (bitArray[i])
                {
                    ushort ushortDeltaButton = (ushort)(1 << i);
                    if ((inputState & ushortDeltaButton) != 0)
                    {
                        DragonMasterIOManagerPy3.Instance.StartCoroutine(ButtonWasPressed(ushortDeltaButton));
                    }
                    else
                    {
                        DragonMasterIOManagerPy3.Instance.StartCoroutine(ButtonWasReleased(ushortDeltaButton));
                    }
                }
            }

            
        }

        /// <summary>
        /// Coroutine that will set our button to true until the end of the frame if it was pressed
        /// </summary>
        /// <param name="buttonID"></param>
        /// <returns></returns>
        private IEnumerator ButtonWasPressed(ushort buttonID)
        {
            ushort buttonIDUshort = (ushort)buttonID;
            this.playerStationInputStatePressed = (ushort)(this.playerStationInputStatePressed | buttonIDUshort);
            yield return new WaitForEndOfFrame();
            this.playerStationInputStatePressed = (ushort)(this.playerStationInputStatePressed & (~buttonIDUshort));
        }

        /// <summary>
        /// Coroutine that will set the value as released for one complete frame
        /// </summary>
        /// <param name="buttonID"></param>
        /// <returns></returns>
        private IEnumerator ButtonWasReleased(ushort buttonID)
        {
            ushort buttonIDUshort = (ushort)buttonID;
            this.playerStationInputStateReleased = (ushort)(this.playerStationInputStateReleased | buttonIDUshort);
            yield return new WaitForEndOfFrame();
            this.playerStationInputStateReleased = (ushort)(this.playerStationInputStateReleased & (~buttonIDUshort));

        }
        #endregion draxboard events

        #region joystick methods
        /// <summary>
        /// This method will assign the appropriate joystick values based on the dead zone and other joystick values that are set
        /// </summary>
        public void SetFromRawJoystickValues(byte rawXAxis, byte rawYAxis)
        {
            if (!persistedValues.SwapJoystickAxisValues)
            {
                joystick_xAxis = rawXAxis;
                joystick_yAxis = rawYAxis;
            }
            else 
            {
                joystick_xAxis = rawYAxis;
                joystick_yAxis = rawXAxis;
            }

            if (persistedValues.invertXAxis)
            {
                joystick_xAxis = (byte)(-(int)joystick_xAxis + 256);
            }
            if (persistedValues.invertYAxis)
            {
                joystick_yAxis = (byte)(-(int)joystick_yAxis + 256);
            }

            if (Mathf.Abs(joystick_xAxis) / 128f < persistedValues.JoystickDeadzone)
            {
                joystick_xAxis = 0;
            }
            if (Mathf.Abs(joystick_yAxis) / 128f < persistedValues.JoystickDeadzone)
            {
                joystick_yAxis = 0;
            }
        }
        #endregion joystick methods

        #region printer events
        /// <summary>
        /// This coroutine will start once we send a print event of any kind to our python application. It should end once we have received a clear flag from our python application
        /// indicating that we have completed a print job.
        /// </summary>
        /// <returns></returns>
        public IEnumerator PrintSentWaitingForResponse()
        {
            printJobQueued = true;
            while (printJobQueued)
            {
                yield return null;
            }
        }
        #endregion printer events

        /// <summary>
        /// Assigns persisted player station values to our player station data object. This should only ever be called from the load function
        /// when this class is first loaded up in our game
        /// </summary>
        public void AssignPersistedPlayerstationDataFromLoad(PersistedPlayerStationValues persistedPlayerStationValuesToAssign)
        {
            if (persistedPlayerStationValuesToAssign == null)
            {
                return;
            }
            this.persistedValues = persistedPlayerStationValuesToAssign;
        }


        /// <summary>
        /// Call this method if there was error received from a device that we should display to the operator
        /// </summary>
        public void OnDeviceErrorRaised()
        {

        }

        /// <summary>
        /// Call this method if an error that we are displaying to the operator has been resolved. This should clear up the message if there are no more errors to report.
        /// </summary>
        public void OnDeviceErrorResolved()
        {

        }
    }

    [System.Serializable]
    /// <summary>
    /// This class will contain values that should be persisted accross play sessions for our player stations.
    /// For example the player station hash and the player station index should be persisted, so that they can be assigned on start
    /// instead of having to calibrate the stations each time the game starts. You may also want to keep values such as joystick
    /// deadzones in here.
    /// </summary>
    private class PersistedPlayerStationValues
    {
        public int PlayerStationIndex; // This is the player number. for an 8 player cabinet this should be a number between 0-7(inclusive)
        public uint PlayerStationHash; // A reference to the associated player station hash. This is the value that our python application will send to correspond player station that it is sending or receiving information about

        public float JoystickDeadzone = .25f; // Any value reported below this threshold will be set to 0. Our joysticks are very sensitive and require this property
        public bool SwapJoystickAxisValues = true; // This will swap our joystick axes meaning that the x axis in game will be the y axis on the controller and vice-versa
        public bool invertXAxis = false; //This will flip left/right on our horizontal axis
        public bool invertYAxis = false; //This will flip our up/down on our vertical axis
    }

    [System.Serializable]
    private class PeripheralSaveData
    {
        /// This will be a list of all the persisted values that each player station will contain. This is to appropriately assign values on start
        public PersistedPlayerStationValues[] PersistedPlayerStationValuesList;
    }
    #endregion player station management classes

    #region threading methods

    /// <summary>
    /// This class will handle all logic that is involved with send and receiving messages from our python application through TCP communication
    /// </summary>
    private class TCPManager
    {

        /// <summary>
        /// If this packet is null, then we are able to receive packets from our python application 
        /// </summary>
        private byte[] currentBytePacketsThatWeHaveReceivedFromPython;
        /// <summary>
        /// If this packet is not null then we will send this packet at the next available time
        /// </summary>
        private byte[] upcomingBytePacketThatWeWillSendToPython;

        public DragonMasterIOManagerPy3 associatedDeviceManager;

        /// <summary>
        /// A queued list of events that we will send to our python application at our next avaialble time
        /// </summary>
        public Queue<byte[]> queuedPacketsToSend = new Queue<byte[]>();

        // Correlates to your local host. This should be the same among every computer
        private readonly IPAddress HOST_ADDRESS = IPAddress.Parse("127.0.0.1");
        // This is the port that we will be receive information from our python application from. This is just an arbirary value. Can be anything but must match what is in python
        private const int RECEIVE_PORT = 25001;
        // This is the port that we will send information to our python application. This is an arbitrary value. Can be anything, but must match with what is in python
        private const int SEND_PORT = 35001;

        #region receive tcp events

        #endregion receive tcp events

        #region send tcp events

        #endregion send tcp events


       
        /// <summary>
        /// 
        /// </summary>
        /// <param name="associatedDeviceManager"></param>
        public TCPManager(DragonMasterIOManagerPy3 associatedDeviceManager)
        {
            this.associatedDeviceManager = associatedDeviceManager;

            Thread thread_ReadEventsFromPython = new Thread(Threaded_ReceiveDataFromPythonApplication);
            thread_ReadEventsFromPython.IsBackground = true;
            thread_ReadEventsFromPython.Start();

            Thread thread_SendEventToPython = new Thread(Threaded_SendDataFromPythonApplication);
            thread_SendEventToPython.IsBackground = true;
            thread_SendEventToPython.Start();
        }

        /// <summary>
        /// This method should take place in the update loop of our IO Manager. It will send a byte packet to our python application if there is one currently waiting to be sent
        /// </summary>
        public void UpdateSendQueuedPythonEventsIfValid()
        {
            if (upcomingBytePacketThatWeWillSendToPython != null)
            {
                return;
            }
            
            if (queuedPacketsToSend.Count == 0)
            {
                return;//If there are no queued packets to send we will not bother setting up the upcoming byte packet.
            }
            List<byte> packetToSend = new List<byte>();
            byte[] currentBytePacket = null;
            while (queuedPacketsToSend.Count > 0)
            {
                currentBytePacket = queuedPacketsToSend.Dequeue();
                for (int i = 0; i < currentBytePacket.Length; i++)
                {
                    packetToSend.Add(currentBytePacket[i]);
                }
            }
            upcomingBytePacketThatWeWillSendToPython = packetToSend.ToArray();
        }

        /// <summary>
        /// This method will read every event that is queued from our python application. It will brek down the events and pass them off to our interpreEventReceveivedFromPython method
        /// </summary>
        public List<byte[]> UpdateReadPythonEventsIfValid()
        {
            if (currentBytePacketsThatWeHaveReceivedFromPython == null)
            {
                return null;
            }

            List<byte[]> allPythonEventsToRead = new List<byte[]>();
            int i = 0;
            ushort sizeOfPacket = 0;
            byte[] eventPacket;
            while (i < currentBytePacketsThatWeHaveReceivedFromPython.Length)
            {
                
                sizeOfPacket = (ushort)(currentBytePacketsThatWeHaveReceivedFromPython[i]);
                i += 1;
                int startOfPacket = i;
                eventPacket = new byte[sizeOfPacket];
                for (int j = 0; j < sizeOfPacket; j++)
                {
                    eventPacket[j] = currentBytePacketsThatWeHaveReceivedFromPython[startOfPacket + j];
                }
                allPythonEventsToRead.Add(eventPacket);
                i += sizeOfPacket;
                

            }
            currentBytePacketsThatWeHaveReceivedFromPython = null;
            return allPythonEventsToRead;
        }

        

        #region threaded methods

        /// <summary>
        /// This thread will run to send queued events to our python application
        /// </summary>
        private void Threaded_SendDataFromPythonApplication()
        {
            int numberOfThreadedLoops = 0;

            IPEndPoint endPoint = new IPEndPoint(HOST_ADDRESS, SEND_PORT);

            Socket socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            

            Socket acceptedSocket = null;
            if (!this.associatedDeviceManager)
            {
                // Debug.Log("I properly exited out Send thread");
                return;
            }

            while (numberOfThreadedLoops < MAX_THREAD_READS_BEFORE_STARTING_NEW_THREAD && this.associatedDeviceManager)
            {
                
                
                try
                {
                    socket.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                    socket.Bind(endPoint);
                    socket.Listen(1);
                    if (this.upcomingBytePacketThatWeWillSendToPython == null)
                    {
                        acceptedSocket = socket.Accept();
                        if (acceptedSocket != null) 
                        {
                            acceptedSocket.Close();
                            acceptedSocket = null;
                        }
                        socket.Disconnect(true);
                        continue;
                    }
                    acceptedSocket = socket.Accept();
                    acceptedSocket.Send(this.upcomingBytePacketThatWeWillSendToPython);

                    this.upcomingBytePacketThatWeWillSendToPython = null;
                    socket.Disconnect(true);
                    acceptedSocket.Close();

                }
                catch (System.Exception e)
                {
                    Debug.LogError(e);
                    if (socket != null)
                    {
                        socket.Close();
                        socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    }
                    if (acceptedSocket != null)
                    {
                        acceptedSocket.Close();
                        acceptedSocket = null;
                    }
                }
                Thread.Sleep(1);
            }

            Thread thread_ReadEventsFromPython = new Thread(Threaded_SendDataFromPythonApplication);
            thread_ReadEventsFromPython.IsBackground = true;
            thread_ReadEventsFromPython.Start();
        }

        /// <summary>
        /// This thread is run to retrieve events from our python application
        /// </summary>
        private void Threaded_ReceiveDataFromPythonApplication()
        {

            int numberOfThreadLoops = 0;
            Socket socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            byte[] bytesBuffer;
            List<byte> totalByteMessage = new List<byte>();
            int bufferedReadSize = 1024;

            if (!this.associatedDeviceManager)
            {
                // Debug.Log("I properly exited out of our threaded method");
                return;
            }

            while (numberOfThreadLoops < MAX_THREAD_READS_BEFORE_STARTING_NEW_THREAD && this.associatedDeviceManager)
            {
                
                if (currentBytePacketsThatWeHaveReceivedFromPython != null)//We will only receive data from our python application if the current packet that we are interpretting is null. This is to avoid conflict with the threads
                {
                    Thread.Sleep(1000/60);
                    continue;
                }
                try
                {
                    socket.Connect(HOST_ADDRESS, RECEIVE_PORT);
                
                    bytesBuffer = new byte[bufferedReadSize];

                    int totalDataReceived = socket.Receive(bytesBuffer, 0, bufferedReadSize, SocketFlags.None);
                    
                    
                    while(totalDataReceived > 0)
                    {
                        for (int i = 0; i < totalDataReceived; i++)
                        {
                            totalByteMessage.Add(bytesBuffer[i]);
                        }
                        totalDataReceived = socket.Receive(bytesBuffer, 0, bufferedReadSize, SocketFlags.None);
                    }

                    socket.Disconnect(true);
                    if (totalByteMessage.Count > 0)
                    {
                        currentBytePacketsThatWeHaveReceivedFromPython = totalByteMessage.ToArray();
                    }
                    totalByteMessage.Clear();
                    ++numberOfThreadLoops;
                }
                catch (System.Exception e)
                {
                    socket.Disconnect(true);
                    socket.Close();
                    socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    Debug.LogError("There was an error reading from our TCP connection");
                    Debug.LogError(e);
                }
                Thread.Sleep(1000/60);
                
            }

            Thread thread_ReadEventsFromPython = new Thread(Threaded_ReceiveDataFromPythonApplication);
            thread_ReadEventsFromPython.IsBackground = true;
            thread_ReadEventsFromPython.Start();
        }

        //
        private byte[] GetSendTCPQueuAsByteArrayAndClear() 
        {
            List<byte> byteListToSend = new List<byte>();
            byte[] eventMessage;
            while (queuedPacketsToSend.Count > 0)
            {
                eventMessage = queuedPacketsToSend.Dequeue();
                foreach (byte b in eventMessage)
                {
                    byteListToSend.Add(b);
                }
            }
            
            return byteListToSend.ToArray();
        }

        //
        public void PrepareBytesToSendThroughTCP()
        {
            if (this.queuedPacketsToSend.Count == 0 || this.upcomingBytePacketThatWeWillSendToPython != null)
            {
                return;
            }
            this.upcomingBytePacketThatWeWillSendToPython = GetSendTCPQueuAsByteArrayAndClear();
        }
        #endregion threaded methods

        /// <summary>
        /// Queues an event to send to our python application
        /// </summary>
        public void QueueEventToSendToPythonApplication(byte[] packetToQueue)
        {
            if (packetToQueue == null || packetToQueue.Length < 1)
            {
                Debug.LogError("Packet to queue was not valid...");
                return;
            }

            queuedPacketsToSend.Enqueue(packetToQueue);
        }

        
        /// <summary>
        /// This will take a byte array that is received from our python application through TCP and break them up into individual events that can be interpreted
        /// by our DragonMasterIOManager.
        /// </summary>
        /// <returns></returns>
        private List<byte[]> BreakUpTCPMessagesIntoIndividualEvents(byte[] rawBytePacketFromPython)
        {
            List<byte[]> allEventsFromBytePacket = new List<byte[]>();


            return allEventsFromBytePacket;
        }
    }
    #endregion threading methods


    #region loading/saving
    private static string PERIPHERAL_SAVE_DIRECTORY
    {
        get 
        {
            return Path.Combine(BookkeepingManager.LinuxPersistentDirectory, "PeripheralSave.dat");
        }
    }

    /// <summary>
    /// Saves the data for our peripheral settings to a binary serialized file
    /// </summary>
    public void SavePeripheralSettings()
    {
        PeripheralSaveData PeripheralSaveData = new PeripheralSaveData();
        PersistedPlayerStationValues[] PersistedPlayerStationValuesList = new PersistedPlayerStationValues[playerStationDataOrderList.Length];
        for (int i = 0; i < playerStationDataOrderList.Length; ++i)
        {
            PersistedPlayerStationValuesList[i] = playerStationDataOrderList[i].persistedValues;
        }

        FileStream fs = new FileStream(PERIPHERAL_SAVE_DIRECTORY, FileMode.Create);

        try 
        {
            BinaryFormatter formatter = new BinaryFormatter();
            formatter.Serialize(fs, PeripheralSaveData);
        }
        catch (SerializationException e)
        {
            Debug.LogError("Error when Serialing our Peripheral Save File");
            Debug.LogError(e);
        }
        catch (Exception e)
        {
            Debug.LogError("Error when Serialing our Peripheral Save File");
            Debug.LogError(e);
        }
        finally
        {
            fs.Close();
        }
    }

    /// <summary>
    /// Loads the data for our periperal settings from a binary serialized file
    /// </summary>
    public void LoadPeripheralSettings()
    {
        PeripheralSaveData peripheralSaveData = null;
        FileStream fs = new FileStream(PERIPHERAL_SAVE_DIRECTORY, FileMode.Open);

        try
        {
            BinaryFormatter formatter = new BinaryFormatter();

            peripheralSaveData = (PeripheralSaveData) formatter.Deserialize(fs);
            
            for (int i = 0; i < Mathf.Min(peripheralSaveData.PersistedPlayerStationValuesList.Length, playerStationDataOrderList.Length); ++i)
            {
                if (peripheralSaveData.PersistedPlayerStationValuesList[i] != null)
                {
                    playerStationDataOrderList[i].AssignPersistedPlayerstationDataFromLoad(peripheralSaveData.PersistedPlayerStationValuesList[i]);
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError("There was an error loading our peripheral settings");
            Debug.LogError(e);
        }
    }
    #endregion loading/saving

    #region debug tools
    public static string ByteArrayToString(byte[] packetArray)
    {
        string byteString = "";
        if (packetArray == null)
        {
            return "Null";
        }
        if (packetArray.Length == 0)
        {
            return "[]";
        }
        byteString = "[";

        for (int i = 0; i < packetArray.Length; i++)
        {
            byteString += packetArray[i];
            if (i < packetArray.Length - 1)
            {
                byteString += ", ";
            }
            else
            {
                byteString += "]";
            }
            
        }
        return byteString;
    }
    #endregion debug tools

    #region device manager logging
    /// This will store logging information about the machine,
    private class DeviceManagerLog
    {
        #region const variables
        private const int MAX_DRAX_EVENTS = 200;
        private const int MAX_JOYSTICK_EVENTS = 100;
        private const int MAX_PRINTER_EVENTS = 100;
        private const int MAX_BILL_ACCEPTOR_EVENTS = 200;
        private const int MAX_OMNIDONGLE_EVENTs = 200;
        #endregion cost variables

        /// Log and save draxboard event at earliest possible time
        public void AddDraxboardEvent(DraxboardLog draxboardLog)
        {

        }

        /// <summary>
        /// Log and save joystick event at earliest possible time
        /// </summary>
        public void AddJoystickEvent(JoystickLog joystickLog)
        {

        }

        /// Log and save printer events at the earliest possible time
        public void AddPrinterEvent(PrinterLog printerLog)
        {

        }

        /// Log and save a bill acceptor event at the earliest possible time
        public void AddBillAcceptorEvent(BillAcceptorLog billAcceptorLog)
        {

        }

        /// Log and save an omnidongle event at the earliest possible time
        public void AddOmnidongleEvent(OmnidongleLog omnidongleLog)
        {

        }
    }

    /// Generic class for logging all device events. This may be needed for debugging purposes in the future if there is
    /// a critical failure along the way.
    private class DeviceLog
    {
        public enum DeviceEvent 
        {
            Other,//This means a different event is taking place aside from the generic events of all devices
            Connected,
            Disconnected,
        }
        public DeviceEvent baseDeviceEvent;
        public DateTime dateTimeLogWasCreated;
        public uint playerStationHash = 0;//Note you will not set a playerstation hash for our omnidongle

        public override string ToString()
        {
            switch (baseDeviceEvent)
            {
                case DeviceEvent.Other:
                    return "";
            }
            return "";
        }


        public virtual string GetDeviceName()
        {
            return "Unassigned Device Name";
        }
    }

    /// 
    private class DraxboardLog : DeviceLog
    {
        public enum DraxEvent
        {
            None,
            DraxInputEvent,
            DraxOutputEvent,//This will come from our python application. This should not be set upon Unity sending an output event. 
            HardMeterEvent,
        }

        public DraxEvent draxboardEvent;
        //Event value can relate to the input, output, or number of ticks that we send to our hard meters
        public ushort eventValue;
        //If the event was sending a
        public byte hardMeterID;

        public override string ToString()
        {
            switch (draxboardEvent)
            {
                case DraxEvent.None:
                    return base.ToString();
                case DraxEvent.DraxInputEvent:
                    return "";
                case DraxEvent.DraxOutputEvent:
                    return "";
                case DraxEvent.HardMeterEvent:
                    return "";
            }
            return "";
        }

        /// Returns the name of the draxboard device that is connected with a 
        public override string GetDeviceName()
        {

            return "Draxboard";
        }
    }

    /// Device Log for our joystick... Since there are not a lot of events to log for our Joystick that would be useful, this
    /// will only record when a joystick has been connected or disconnected. Making a separate class in case there is a reason to log somethig
    private class JoystickLog : DeviceLog
    {

        public override string GetDeviceName()
        {
            return "Joystick";
        }
    }

    /// Logs of bill acceptor events. This can include Bill inserted rejected, returned, bill acceptor state changes etc...
    private class BillAcceptorLog : DeviceLog
    {
        public enum BillAcceptorEvent
        {
            None,
            BillAcceptorState,
            BillInserted,
            BillStacked,//Bill has been accepted
            BillRejected,
            BillReturned,

        }

        public BillAcceptorEvent billAcceptorEvent;
        public byte valueOfBill;//If the event does not involve a bill value, this should be set to 0

        public override string GetDeviceName()
        {
            return "Bill Acceptor";
        }
    }

    /// Extension of our printer class that will be used to log events
    private class PrinterLog : DeviceLog
    {
        public enum PrinterEvent
        {
            None,
            PrintEventSent,
            PrintEventSuccess,
            PrintEventFailed,
            StateChange,
        }

        /// This should match the event byte that we use to send a print event to our python application
        /// For example if this was a voucher ticket, this should equal 0x41 or 'PRINT_CASHOUT_TICKET'
        public byte printEventCode;
        /// The state of our printer at that moment
        public uint printerState;
        /// The status or amount of paper remaining, This will typically be sent in the same method as our printer state event unless that changes in the future
        public uint paperStatus;


    }

    /// <summary>
    /// Log of Omnidongle events. This will include connection/disconnection events, as well as message send, message receive
    /// </summary>
    private class OmnidongleLog
    {
        public enum OmnidongleEvent
        {
            None,
            MessageSend,//Messages that we send to the omnidongle
            MessageReceive,//Messages that we receive from our omnidongle
        }
        private OmnidongleEvent omnidongleEvent;
        public byte[] omnidongleByteMessage = null;
    }

    
    #endregion device manager logging

    #region persisted player station information


    #endregion persisted player station information

    #region debug methods
    
    #endregion debug methods
}
