from requests_retry import requests_retry_session

class Job:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def jobs_response(response, link, logger):
    if link["type"] == "greenhouse" or link["type"] == "jobscore":
        return response.json()["jobs"]
    elif link["type"] == "ultipro":
        return response.json()["opportunities"]
    elif link["type"] == "adp":
        return response.json()["jobRequisitions"]
    elif link["type"] == "lever":
        return response.json()
    elif link["type"] == "smartrecruiters":
        result = response.json()["content"]
        offset = 0
        total = response.json()["totalFound"]
        while total - offset > 100:
            offset += 100
            try:
                partial = requests_retry_session().get("{}?offset={}".format(link["url"], offset), timeout=2)
                result.extend(partial.json()["content"])
            except Exception as x:
                logger.error("{} : {}".format(repr(x), "{}?offset={}".format(link["url"], offset)))
                continue
        return result


def create_job(job, link):
    if link["type"] == "greenhouse":
        city = job.get("location", {}).get("name", "") or ""
        return Job(
            title=job.get("title", "").rstrip(),
            id=str(job["id"]),
            location=city.rstrip(),
            url=job.get("absolute_url", "").rstrip())
    elif link["type"] == "lever":
        return Job(
            title=job.get("text", "").rstrip(),
            id=str(job["id"]),
            location=job.get("categories", {}).get("location", "").rstrip(),
            url=job.get("hostedUrl", "").rstrip())
    elif link["type"] == "jobscore":
        return Job(
            title=job.get("title", "").rstrip(),
            id=str(job["id"]),
            location=job.get("location", "").rstrip(),
            url=job.get("detail_url", "").rstrip())
    elif link["type"] == "ultipro":
        city = job.get("Locations", [{}])[0].get("Address", {}).get("City", "") or ""
        return Job(
            title=job.get("Title", "").rstrip(),
            id=str(job["Id"]),
            location=city.rstrip(),
            url=link["url"].rstrip("JobBoardView/LoadSearchResults") + "/OpportunityDetail?opportunityId=" + str(job["Id"]))
    elif link["type"] == "adp":
        city = job.get("requisitionLocations", [{}])[0].get("address", {}).get("cityName", "") or ""
        return Job(
            title=job.get("requisitionTitle", "").rstrip(),
            id=str(job["itemID"]),
            location=job.get("location", "").rstrip(),
            url=link["url"].replace("careercenter/public/events/staffing/v1/job-requisitions", "mdf/recruitment/recruitment.html") + "&jobId=" + str(job["customFieldGroup"]["stringFields"][0]["stringValue"]))
    elif link["type"] == "smartrecruiters":
        return Job(
            title=job.get("name", "").rstrip(),
            id=str(job["id"]),
            location=job.get("location", {}).get("city", "").rstrip(),
            url="https://jobs.smartrecruiters.com/{}/{}".format(job["company"]["identifier"], job["id"]))
