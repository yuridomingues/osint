# Import schemas

## Generic public observations

Endpoint:

`POST /cases/{case_id}/observations`

Body:

```json
{
  "observations": [
    {
      "platform": "github",
      "handle": "example",
      "profile_url": "https://github.com/example",
      "display_name": "Example",
      "bio": "Public profile text",
      "external_urls": ["https://example.org"],
      "media_hashes": []
    }
  ]
}
```

## Sherlock CSV

Endpoint:

`POST /cases/{case_id}/tool-import`

```json
{
  "tool": "sherlock_csv",
  "content": "username,name,url_main,url_user,exists,http_status,response_time_s\n..."
}
```

Only rows represented as claimed/found are normalized into account observations.

## Maigret JSON/NDJSON

Endpoint:

`POST /cases/{case_id}/tool-import`

```json
{
  "tool": "maigret_json",
  "content": "{...}\n{...}"
}
```

The adapter accepts common JSON, NDJSON and object-map shapes and extracts public account URL, handle, display name, biography and public links when present.

## Public-post coordination dataset

Endpoint:

`POST /cases/{case_id}/posts`

```json
{
  "posts": [
    {
      "platform": "example-platform",
      "author_handle": "account_a",
      "url": "https://example.org/post/1",
      "text": "Public post content",
      "published_at": "2026-09-11T12:00:00Z"
    }
  ]
}
```

The built-in detector only escalates exact normalized-content clusters with at least three distinct accounts and a short temporal spread.
