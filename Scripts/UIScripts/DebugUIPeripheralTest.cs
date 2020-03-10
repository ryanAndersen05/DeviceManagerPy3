using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class DebugUIPeripheralTest : MonoBehaviour {
	#region const variables
	private const float TIME_BETWEEN_UPDATES = .75f;
	#endregion const variables

	#region static variables
	public static DebugUIPeripheralTest Instance
	{
		get 
		{
			if (instance == null)
			{
				instance = GameObject.FindObjectOfType<DebugUIPeripheralTest>();
			}
			return instance;
		}
	}

	private static DebugUIPeripheralTest instance;
	#endregion static variables

	#region main variables
	public DebugPlayerStationInfo[] playerStationInfoList;

	private float timeBeforeNextUpdate;
	#endregion main variables

	#region monobehaviour methods
	private void Awake()
	{
		instance = this;
		for (int i = 0; i < playerStationInfoList.Length; ++i)
		{
			playerStationInfoList[i].playerStationIndexInOverseer = i;//Assign debug player station properties at the start
		}
	}

	private void Update()
	{
		UpdateAllPlayerStationInfoScreens();
		// if (timeBeforeNextUpdate <= 0)
		// {
		// 	timeBeforeNextUpdate += TIME_BETWEEN_UPDATES;
		// 	UpdateAllPlayerStationInfoScreens();
		// }
		// timeBeforeNextUpdate -= Time.unscaledDeltaTime;
	}
	#endregion monobehaviour

	#region debug methods
	private void UpdateAllPlayerStationInfoScreens()
	{
		for (int i = 0; i < playerStationInfoList.Length; i++)
		{
			playerStationInfoList[i].UpdatePlayerStationInfo();
		}
	}
	#endregion debug methosd
}
