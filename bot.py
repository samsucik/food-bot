import requests
import os
import time
from slackclient import SlackClient
import json
import base64
from pygame import mixer

slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
starterbot_id = None
RTM_READ_DELAY = 1  # 1 second delay between reading from RTM


def parse_bot_commands(slack_events):
    file_name = "saved_img.jpg"
    target_labels = ["food", "drink", "dessert", "cake", "fruit", "berry", "meal", "brunch", "breakfast", "cookie"]
    thumb_keys = ["thumb_720", "thumb_480", "thumb_360", "url_private_download"]
    
    for event in slack_events:
        if event["type"] == "file_shared":
            payload = {
                'token': os.environ.get('SLACK_BOT_TOKEN'),
                'file': event['file_id']
            }
            r = requests.get(
                "https://slack.com/api/files.info", params=payload)
            file_info = json.loads(r.text)
            image_url = None
            for thumb_key in thumb_keys:
                if thumb_key in file_info["file"]:
                    image_url = file_info["file"][thumb_key]
                    break
                
            saved = download_image(image_url, file_name)
            if saved:
                labels = analyse_image(file_name)
                if labels:
                    found_labels = [l for l in target_labels if l in labels]
                    msg_info = file_info["file"]["shares"]["public"] \
                               if "public" in file_info["file"]["shares"] \
                               else file_info["file"]["shares"]["private"]
                    instances = [(k, v[0]["ts"]) for k, v in msg_info.items()]
                    reaction_target = instances
                    return found_labels, reaction_target
            else:
                pass
    return None, None


def download_image(url, file_name):
    r = requests.get(url, headers={"Authorization": "Bearer " + os.environ.get('SLACK_BOT_TOKEN')})
    try:
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
        return True
    except Exception as e:
        return False


def analyse_image(file_name):
    img = None
    with open(file_name, "rb") as image_file:
        img = base64.b64encode(image_file.read()).decode('UTF-8')
    payload = {
      "requests":[
        {
          "image":{
            "content": img
          },
          "features":[
            {
              "type":"LABEL_DETECTION",
              "maxResults": 5
            }
          ]
        }
      ]
    }
    request_file = "vision_request.json"
    with open(request_file, 'w') as output_file:
        json.dump(payload, output_file)
    data = open(request_file, 'rb').read()

    api_key = "AIzaSyDi41pOBb4K3zjr8ruYXIEveUAcDfDd3SQ"
    vision_r = requests.post("https://vision.googleapis.com/v1/images:annotate?key=" + api_key,
                             data=data,
                             headers={'Content-Type': 'application/json'})
    if vision_r.status_code == 200:
        labels = json.loads(vision_r.text)["responses"][0]["labelAnnotations"]
        labels = [label["description"] for label in labels]
        return labels
    else:
        print("call to vision API failed")
        print(vision_r.status_code)
        print(vision_r.text)
        return None
    

def act(labels, reaction_target, channel_reporting="GC9CLRKFH"):
    message = "There is {}!!!".format(" and ".join(labels))
    thanks_message = "Ooooh, that's yummy!"
    print(message)
    
    mixer.init()
    mixer.music.load('alarm.mp3')
    mixer.music.play()
    
    slack_client.api_call(
        "chat.postMessage",
        channel=channel_reporting,
        text=message
    )

    slack_client.api_call(
        "chat.postMessage",
        channel=reaction_target[0][0],
        thread_ts=reaction_target[0][1],
        text=thanks_message
    )

    slack_client.api_call(
        "reactions.add",
        channel=reaction_target[0][0],
        name="star-struck",
        timestamp=reaction_target[0][1]
    )
    return

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            found_labels, reaction_target = parse_bot_commands(slack_client.rtm_read())
            if found_labels is not None and len(found_labels) > 0:
                act(found_labels, reaction_target)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
