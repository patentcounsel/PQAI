"""
This module hides the implementation details of the document storage
"""
import os
import re
import json
import boto3
import botocore.exceptions
from pymongo import MongoClient

MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_PORT = os.environ["MONGO_PORT"]
MONGO_USER = os.environ["MONGO_USER"]
MONGO_PASSWORD = os.environ["MONGO_PASSWORD"]
MONGO_DBNAME = os.environ["MONGO_DBNAME"]
MONGO_PAT_COLL = os.environ["MONGO_PAT_COLL"]
MONGO_NPL_COLL = os.environ["MONGO_NPL_COLL"]
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
PQAI_S3_BUCKET_NAME = os.environ["PQAI_S3_BUCKET_NAME"]

S3_CREDENTIALS = {
    "aws_access_key_id": AWS_ACCESS_KEY_ID,
    "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
}

BOTO_CLIENT = boto3.client("s3", **S3_CREDENTIALS)
if MONGO_USER and MONGO_PASSWORD:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"

MONGO_CLIENT = MongoClient(MONGO_URI)
PAT_COLL = MONGO_CLIENT[MONGO_DBNAME][MONGO_PAT_COLL]
NPL_COLL = MONGO_CLIENT[MONGO_DBNAME][MONGO_NPL_COLL]


def get_patent_data(pn, only_bib=False):
    """Retrieve a patent's data from the database.

    Args:
        pn (str): Publication number, as it is in the database.
        only_bib (bool, optional): Return only bibliography (as opposed to all
            details such as claims, description, etc.)

    Returns:
        dict: The patent data, keys are patent fields. If no patent is found
            matching the patent number, `None` is returned.
    """
    if only_bib:
        return get_patent_data_from_mongo_db(pn)
    return get_patent_data_from_s3(pn)

def get_patent_data_from_mongo_db(pn):
    """Retrieve patent's bibliography from Mongo DB"""
    query = {"publicationNumber": pn}
    patent = PAT_COLL.find_one(query)
    return patent

def get_patent_data_from_s3(pn):
    """Retrieve the patent's data in its entirety from S3 bucket"""
    try:
        bucket = PQAI_S3_BUCKET_NAME
        key = f"patents/{pn}.json"
        obj = BOTO_CLIENT.get_object(Bucket=bucket, Key=key)
        contents = obj["Body"].read().decode()
        return json.loads(contents)
    except botocore.exceptions.ClientError:
        return None

def get_bibliography(pn):
    """Return bibliography details of the patent"""
    return get_patent_data(pn, only_bib=True)

def get_full_text(pn):
    """Return concatenated abstract, claims, and description of a patent"""
    patent = get_patent_data(pn, only_bib=False)
    if patent is None:
        return None
    abstract = patent["abstract"]
    claims = "\n".join(patent["claims"])
    desc = patent["description"]
    desc = re.sub(r"\n+(?=[^A-Z])", " ", desc)  # collapse multiple line breaks
    text = "\n".join([abstract, claims, desc])
    return text

def get_cpcs(pn):
    """Get a patent's CPCs"""
    patent = get_patent_data(pn, only_bib=False)
    return patent.get("cpcs") if patent is not None else None

def get_claims(pn):
    """Return claims of the patent as a list"""
    patent_data = get_patent_data(pn)
    if not patent_data:
        raise Exception(f"Patent number {pn} missing in database.")
    if not patent_data.get("claims"):
        raise Exception(f"Claims for {pn} missing in database.")
    return patent_data.get("claims")

def get_first_claim(pn):
    """Return first claim of the patent"""
    first_claim = get_claims(pn)[0]
    return first_claim

def get_document(doc_id):
    """Get a document (patent or non-patent) by its identifier"""
    if re.match(r"US\d+", doc_id):
        return PAT_COLL.find_one({"publicationNumber": doc_id})
    return NPL_COLL.find_one({"id": doc_id})
