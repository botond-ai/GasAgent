Add a new tool called JSON_creator, which should contain the following information: 
-Generate a ticket number, sequentially increasing starting from TK001, store it in Json. 
-Also store The user's name
-the time when he contacted
-The language of the original message being identified
-the original message the user sent
-the issue type, which has been identified
-The owning team 
-the xlsx file name, which is being referred to
-the priority of the issue identified
-the acknowledgement time
-The resolve time
-The cost for the customer
-The EUR/1 USD currency exchange rate
--The HUF/1 USD currency exchange rate
-The notes and dependencies belonging to that issue
-The sentiment of the person's feelings
-The sentiment confidence level
-The entire conversation including the original message and the entire response

The tool should create a JSON, and in the message's tools used section after all the other tools mentioned, there should be another line mentioning that the JSON tool has been used. On click of that line, there should be a dropdown with the entire JSON captured.