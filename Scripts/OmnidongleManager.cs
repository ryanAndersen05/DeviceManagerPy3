using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class OmnidongleManager : MonoBehaviour {

	#region static variables
	private static OmnidongleManager instance;

	public static OmnidongleManager Instance
	{
		get
		{
			if (instance == null)
			{
				instance = GameObject.FindObjectOfType<OmnidongleManager>();
			}
			return instance;
		}
	}
	#endregion static variables

	#region monobheaviour methods
	private void Awake()
	{
		instance = this;
	}
	#endregion monobehaviour methods

	#region placeholder dongle events
	//This method will be called anytime we receive a message that our omnidongle has been connected
	public void OmnidongleDeviceConnected()
	{

	}

	//This method will be called anytime we receive a message that our dongle has been disconnected
	public void OmnidongleDeviceDisconnected()
	{

	}

	//This method will be called anytime we receive a message from our omnidongle
	public void ReceiveDataFromOmnidongle(byte[] byteReceivePacketFromOmnidongle)
	{

	}
	#endregion placeholder dongle events
}
