using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Overseer : MonoBehaviour {

	#region static variables
	private static Overseer instance;

	public static Overseer Instance
	{
		get
		{
			if (instance == null)
			{
				instance = GameObject.FindObjectOfType<Overseer>();
			}
			return instance;
		}
	}
	#endregion static variables

    #region main variables
    public Player[] players
    #endregion main variables

	#region monobheaviour methods
	private void Awake()
	{
		instance = this;
	}
	#endregion monobehaviour methods
}
