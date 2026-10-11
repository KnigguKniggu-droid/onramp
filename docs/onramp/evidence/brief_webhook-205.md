While testing Healthchecks with a personal project, I set up a webhook integration whose endpoint answers with HTTP 205 (Reset Content). When a check changes state, my endpoint receives three identical requests, and the integration is marked as failed with "Received status code 205".

I reproduced it locally: the integration's "Test" button also reports an error for the same endpoint, although it only sends one request.

Expected: a 2xx response such as 205 means the notification was delivered; it should not be retried or reported as a failure.
