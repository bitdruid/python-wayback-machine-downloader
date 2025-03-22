import http.client
from datetime import datetime, timezone

from importlib.metadata import version

from pywaybackup.helper import url_get_timestamp
from pywaybackup.Verbosity import Verbosity as vb

# def startup():
#     try:
#         vb.write(message=f"\n<<< python-wayback-machine-downloader v{version('pywaybackup')} >>>")
        
#         if Database.QUERY_EXIST:
#             vb.write(message=f"\nSAVE job exist - processed {Database.QUERY_PROGRESS}\nResuming save... (to reset the job use '--reset')\n")

#             for i in range(5, -1, -1):
#                 vb.write(message=f"\r{i}...")
#                 print("\033[F", end="")
#                 print("\033[K", end="")           

#                 time.sleep(1)

#             #vb.write(message="\n")
#     except KeyboardInterrupt:
#         os._exit(1)

# GET: store page to wayback machine and response with redirect to snapshot
# POST: store page to wayback machine and response with wayback machine status-page
# tag_jobid = '<script>spn.watchJob("spn2-%s", "/_static/",6000);</script>'
# tag_result_timeout = '<p>The same snapshot had been made %s minutes ago. You can make new capture of this URL after 1 hour.</p>'
# tag_result_success = ' A snapshot was captured. Visit page: <a href="%s">%s</a>'
def save_page(url: str):
    """
    Saves a webpage to the Wayback Machine. 

    Args:
        url (str): The URL of the webpage to be saved.

    Returns:
        None: The function does not return any value. It only prints messages to the console.
    """
    try:
        connection = http.client.HTTPSConnection("web.archive.org")
        headers = {"User-Agent": f"bitdruid-python-wayback-downloader/{version('pywaybackup')}"}
        vb.write(message="\nSaving page to the Wayback Machine...")
        connection.request("GET", f"https://web.archive.org/save/{url}", headers=headers)
        vb.write(message=f"\n-----> Request sent -> URL: {url}")
        response = connection.getresponse()
        response_status = response.status

        if response_status == 302:
            location = response.getheader("Location")
            snapshot_timestamp = datetime.strptime(url_get_timestamp(location), '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
            current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            timestamp_difference = (datetime.strptime(current_timestamp, '%Y-%m-%d %H:%M:%S') - datetime.strptime(snapshot_timestamp, '%Y-%m-%d %H:%M:%S')).seconds / 60
            timestamp_difference = int(round(timestamp_difference, 0))

            if timestamp_difference < 1:
                vb.write(message="\n-----> Response: 302 (new snapshot)")
                vb.write(status="SNAPSHOT", type="URL", message=f"{location}")
            elif timestamp_difference >= 1:
                vb.write(message=f"\n-----> Response: 302 (existing snapshot - wait for {60 - timestamp_difference} minutes)")
                vb.write(status="SNAPSHOT", type="URL", message=f"{location}")
                vb.write(status="WAYBACK", type="TIME", message=f"{snapshot_timestamp}")
                vb.write(status="REQUEST", type="TIME", message=f"{current_timestamp}")

        elif response_status == 429:
            vb.write(message="\n-----> Response: 429 (too many requests)")
            vb.write(message="- no simultaneous allowed")
            vb.write(message="- 15 per 5 minutes\n")
        elif response_status == 520:
            vb.write(message="\n-----> Response: 520 (job failed)")
        elif response_status == 404:
            vb.write(message="\n-----> Response: 404 (not found)")
        else:
            vb.write(message=f"\n-----> Response: {response_status} - UNHANDLED")

        connection.close()
    except ConnectionRefusedError:
        vb.write(message="\nCONNECTION REFUSED -> could not connect to wayback machine")

