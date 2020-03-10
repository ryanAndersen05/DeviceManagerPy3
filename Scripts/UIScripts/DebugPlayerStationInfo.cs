using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// This is a component that will display the properties of the associated player station
/// </summary>
public class DebugPlayerStationInfo : MonoBehaviour {
	public int playerStationIndexInOverseer {get; set;}

	public Text playerStationTextBox;
	

	#region monobehaviour methods
	private void Awake()
	{
		
	} 
	#endregion monobehaviour methods

	/// This method will update all the important information of the associated player station
	public void UpdatePlayerStationInfo() 
	{
		DragonMasterIOManagerPy3 cachedIO = DragonMasterIOManagerPy3.Instance;
		if (cachedIO == null)
		{
			Debug.LogError("DragonMasterIOManagerPy3 object is null. This should not be the case.");
			return;
		}

		string playerStationInfoString = "";

		playerStationInfoString += "Player Station Index: " + playerStationIndexInOverseer.ToString() + '\n';
		playerStationInfoString += "Player Station Hash: " + cachedIO.GetPlayerStationHashFromPlayerStationIndex(playerStationIndexInOverseer) + '\n';
		playerStationInfoString += "Input State: " + cachedIO.GetInputStateForPlayerStation(playerStationIndexInOverseer) + '\n';
		playerStationInfoString += "Output State: " + cachedIO.GetDraxOutputStateForPlayerStation(playerStationIndexInOverseer) + '\n';
		playerStationInfoString += "Joystick Name: " + cachedIO.GetJoystickType(playerStationIndexInOverseer).ToString() + '\n';
		playerStationInfoString += "Joystick Axes: X: " + cachedIO.GetHorizontalJoystickAxis(playerStationIndexInOverseer).ToString("0.00") +
			" Y: " + cachedIO.GetVerticalJoystickAxis(playerStationIndexInOverseer).ToString("0.00") + '\n';
		playerStationInfoString += "Bill Acceptor Name: " + cachedIO.GetBillAcceptorType(playerStationIndexInOverseer).ToString() + '\n';
		playerStationInfoString += "Bill Acceptor State: " + cachedIO.GetBillAcceptorState(playerStationIndexInOverseer) + '\n';
		playerStationInfoString += "Printer Name: " + cachedIO.GetPrinterType(playerStationIndexInOverseer).ToString() + '\n';

		playerStationTextBox.text = playerStationInfoString;
	}
}
