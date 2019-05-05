import sendgrid
import os
import json
import requests
import MySQLdb
import logging
from datetime import datetime
from sendgrid.helpers.mail import *
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def requests_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

logFormatter = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logFormatter, level=logging.DEBUG)
logger = logging.getLogger(__name__)

filter_words = set(json.loads(os.environ['FILTER_WORDS']))
blacklist = set(json.loads(os.environ['BLACKLIST']))

mydb = MySQLdb.connect(host=os.environ['MARIADB_HOSTNAME'],
    user=os.environ['MARIADB_USERNAME'],
    passwd=os.environ['MARIADB_PASSWORD'],
    db=os.environ['MARIADB_DATABASE'])
cursor = mydb.cursor()

cursor.execute("select * from greenhouse_links")
greenhouse = [{'name': item[1], 'url': item[2]} for item in cursor.fetchall()]
cursor.execute("select * from lever_links")
lever = [{'name': item[1], 'url': item[2]} for item in cursor.fetchall()]
cursor.execute("select * from jobscore_links")
jobscore = [{'name': item[1], 'url': item[2]} for item in cursor.fetchall()]
cursor.execute("select * from greenhouse")
greenhouse_list = [item[0] for item in cursor.fetchall()]
cursor.execute("select * from lever")
lever_list = [item[0] for item in cursor.fetchall()]
cursor.execute("select * from jobscore")
jobscore_list = [item[0] for item in cursor.fetchall()]

email_list = []

for g in greenhouse:
    try:
        response = requests_retry_session().get(g["url"], timeout=2)
    except Exception as x:
        logger.error("{} : {}".format(x.__class__.__name__, g["url"]))
        continue

    if response.status_code != 200:
        logger.error("Status: {}, Headers: {}, Error Response: {}, Url: {}".format(response.status_code, response.headers, response.text, g["url"]))
        continue

    for job in response.json()["jobs"]:
        if any([x in job["title"].lower() for x in filter_words]) and not any([x in job["title"].lower() for x in blacklist]) and str(job["id"]) not in greenhouse_list:
            email_list.append("{} - {}({}): {}".format(g["name"], job["title"], job["location"]["name"], job["absolute_url"]))
            try:
                cursor.execute("INSERT INTO greenhouse(`id`) VALUES('{}')".format(job["id"]))
                mydb.commit()
            except Exception as x:
                logger.error("{} : {}".format(x.__class__.__name__, g["url"]))
                continue

for l in lever:
    try:
        response = requests_retry_session().get(l["url"], timeout=2)
    except Exception as x:
        logger.error("{} : {}".format(x.__class__.__name__, l["url"]))
        continue

    if response.status_code != 200:
        logger.error("Status: {}, Headers: {}, Error Response: {}, Url: {}".format(response.status_code, response.headers, response.text, l["url"]))
        continue
        
    for job in response.json():
        if any([x in job["text"].lower() for x in filter_words]) and not any([x in job["text"].lower() for x in blacklist]) and str(job["id"]) not in lever_list:
            email_list.append("{} - {}({}): {}".format(l["name"], job["text"], job["categories"]["location"], job["hostedUrl"]))
            try:
                cursor.execute("INSERT INTO lever(`id`) VALUES('{}')".format(job["id"]))
                mydb.commit()
            except Exception as x:
                logger.error("{} : {}".format(x.__class__.__name__, l["url"]))
                continue

for j in jobscore:
    try:
        response = requests_retry_session().get(j["url"], timeout=2)
    except Exception as x:
        logger.error("{} : {}".format(x.__class__.__name__, j["url"]))
        continue

    if response.status_code != 200:
        logger.error("Status: {}, Headers: {}, Error Response: {}, Url: {}".format(response.status_code, response.headers, response.text, j["url"]))
        continue

    for job in response.json()["jobs"]:
        if any([x in job["title"].lower() for x in filter_words]) and not any([x in job["title"].lower() for x in blacklist]) and str(job["id"]) not in jobscore_list:
            email_list.append("{} - {}({}): {}".format(j["name"], job["title"], job["location"], job["detail_url"]))
            try:
                cursor.execute("INSERT INTO jobscore(`id`) VALUES('{}')".format(job["id"]))
                mydb.commit()
            except Exception as x:
                logger.error("{} : {}".format(x.__class__.__name__, j["url"]))
                continue

cursor.close()
now = datetime.now()

if email_list:
    sg = sendgrid.SendGridAPIClient(apikey=os.environ['SENDGRID_API_KEY'])
    from_email = Email(os.environ['FROM_EMAIL'], os.environ['FROM_NAME'])
    to_email = Email(os.environ['TO_EMAIL'])
    subject = "Internships & Co-ops - {}".format(now.strftime("%x"))
    content = Content("text/plain", "\n\n".join(email_list))
    mail = Mail(from_email, subject, to_email, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    logger.info(response.status_code)
    logger.info(response.body)
    logger.info(response.headers)
else:
    logger.info("No new jobs for: {}".format(now.strftime("%m/%d/%Y, %H:%M:%S"))
