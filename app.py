import sendgrid
import os
import json
import pymysql
import logging
import sentry_sdk
from Job import jobs_response, create_job
from datetime import datetime
from sendgrid.helpers.mail import *
from requests_retry import requests_retry_session

sentry_sdk.init(dsn=os.environ['SENTRY'])
logFormatter = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logFormatter, level=logging.DEBUG)
logger = logging.getLogger(__name__)

filter_words = set(json.loads(os.environ['FILTER_WORDS']))
blacklist = set(json.loads(os.environ['BLACKLIST']))

mydb = pymysql.connect(host=os.environ['MARIADB_HOSTNAME'],
    user=os.environ['MARIADB_USERNAME'],
    passwd=os.environ['MARIADB_PASSWORD'],
    db=os.environ['MARIADB_DATABASE'])
cursor = mydb.cursor()

cursor.execute("call links()")
links_list = [{'name': item[0], 'url': item[1], 'type': item[2]} for item in cursor]
cursor.execute("call completed()")
completed_list = [item[0] for item in cursor]

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
        try:
            job = create_job(job, link)
        except Exception as x:
            logger.error("{} : {}".format(repr(x), link["url"]))
            continue
        if job.id not in completed_list and any(x in job.title.lower() for x in filter_words) and not any(x in job.title.lower() for x in blacklist):
            email_list.append("{} - {} ({}): {}".format(link["name"], job.title, job.location, job.url))
            try:
                cursor.execute("INSERT INTO {}(`id`) VALUES('{}')".format(link["type"], job.id))
                mydb.commit()
            except Exception as x:
                logger.error("{} : {}, id={}".format(repr(x), link["url"], job.id))
                continue

cursor.close()
now = datetime.now()

if email_list:
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
else:
    logger.info("No new jobs for: {}".format(now.strftime("%m/%d/%Y, %H:%M:%S")))
