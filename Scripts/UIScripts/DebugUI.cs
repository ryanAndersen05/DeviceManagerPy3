using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DebugUI : MonoBehaviour {
	#region static variables
	private static DebugUI instance;

	public static DebugUI Instance
	{
		get 
		{
			if (instance == null)
			{
				instance = GameObject.FindObjectOfType<DebugUI>();
			}
			return instance;
		}
	}
	#endregion static variables
	public UnityEngine.UI.Text debugTextElement;

	private List<MessageContainer> listOfDebugMessages = new List<MessageContainer>();

	private Queue<MessageContainer> asyncQueuedMessages = new Queue<MessageContainer>();

	#region monobehaviour methods
	private void Awake()
	{
		instance = this;
		UpdateMessageDisplay();
	}

	private void Update()
	{
		while (asyncQueuedMessages.Count > 0)
		{
			MessageContainer message = asyncQueuedMessages.Dequeue();
			AddMessageToList(message);
			StartCoroutine(DisplayMessageForSecondsCoroutine(message, message.timeInSecondsToDisplay));
		}
	}
	#endregion monobehaviour methods

	private void UpdateMessageDisplay()
	{
		string debugMessage = "";
		foreach (MessageContainer message in listOfDebugMessages)
		{
			debugMessage += message.messageText + '\n';
		}
		debugTextElement.text = debugMessage;
	}

	public void AddMessageForSeconds(string messageToDisplay, float timeInSeconds = 3)
	{
		MessageContainer message = new MessageContainer(messageToDisplay);
		AddMessageToList(message);
		StartCoroutine(DisplayMessageForSecondsCoroutine(message, timeInSeconds));
	}

	public void AddMessageForSecondsAsync(string messageToDisplay, float timeInSeconds = 3)
	{
		MessageContainer message = new MessageContainer(messageToDisplay);
		message.timeInSecondsToDisplay = timeInSeconds;
		asyncQueuedMessages.Enqueue(message);
	}


	private IEnumerator DisplayMessageForSecondsCoroutine(MessageContainer message, float timeToDisplayMessage)
	{
		
		yield return new WaitForSecondsRealtime(timeToDisplayMessage);
		RemoveMessageFromList(message);
	}

	private void AddMessageToList(MessageContainer message)
	{
		listOfDebugMessages.Add(message);
		UpdateMessageDisplay();
	}

	private void RemoveMessageFromList(MessageContainer message)
	{
		if (listOfDebugMessages.Contains(message))
		{
			listOfDebugMessages.Remove(message);
		}
		UpdateMessageDisplay();
	}

	///Container class that contains properties for our message
	private class MessageContainer
	{
		public Color textColor;
		public string messageText;
		public float timeInSecondsToDisplay;

		public MessageContainer(string messageText) : this(messageText, Color.red)
		{

		}

		public MessageContainer(string messageText, Color textColor)
		{
			this.messageText = messageText;
			this.textColor = textColor;
		}
	}
}
