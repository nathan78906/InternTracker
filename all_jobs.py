import sendgrid
import os
import json
import pymysql
import logging
import sentry_sdk
import argparse
from Job import jobs_response, create_job
from datetime import datetime
from sendgrid.helpers.mail import *
from requests_retry import requests_retry_session

parser = argparse.ArgumentParser()
parser.add_argument("--filter_words", help="pass in optional filter words")
parser.add_argument("--blacklist", help="pass in optional blacklist")
args = parser.parse_args()

sentry_sdk.init(dsn=os.environ['SENTRY'])
logFormatter = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logFormatter, level=logging.DEBUG)
logger = logging.getLogger(__name__)

filter_words = set(json.loads(args.filter_words)) if args.filter_words else set(json.loads(os.environ['FILTER_WORDS']))
blacklist = set(json.loads(args.blacklist)) if args.blacklist else set(json.loads(os.environ['BLACKLIST']))

mydb = pymysql.connect(host=os.environ['MARIADB_HOSTNAME'],
    user=os.environ['MARIADB_USERNAME'],
    passwd=os.environ['MARIADB_PASSWORD'],
    db=os.environ['MARIADB_DATABASE'])
cursor = mydb.cursor()

cursor.execute("call links()")
links_list = [{'name': item[0], 'url': item[1], 'type': item[2]} for item in cursor]
cursor.close()

email_list = []

for link in links_list:
    try:
        response = requests_retry_session().get(link["url"], timeout=10)
    except Exception as x:
        logger.error("{} : {}".format(repr(x), link["url"]))
        continue

    if response.status_code != 200:
        logger.error("{} : {}".format(response.status_code, link["url"]))
        continue

    for job in jobs_response(response, link, logger):
        job = create_job(job, link)
        filter_check = job.title.lower() + job.location.lower()
        if any(x in filter_check for x in filter_words) and not any(x in filter_check for x in blacklist):
            email_list.append("{} - {} ({}): {}".format(link["name"], job.title, job.location, job.url))

now = datetime.now()

sg = sendgrid.SendGridAPIClient(api_key=os.environ['SENDGRID_API_KEY'])
from_email = From(os.environ['FROM_EMAIL'], os.environ['FROM_NAME'])
to_email = To(os.environ['TO_EMAIL'])
subject = "Jobs - {}".format(now.strftime("%x"))
content = Content("text/plain", "\n\n".join(email_list))
mail = Mail(from_email, to_email, subject, content)
response = sg.send(mail)
logger.info(response.status_code)
logger.info(response.body)
logger.info(response.headers)
