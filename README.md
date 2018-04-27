# substweet

Post GIFs of a video with subtitles to twitter.

# INSTALL
To use this application you need:

- A recent version of [ffmpeg](https://www.ffmpeg.org/download.html)
- Python >= 3.5
- Credentials from [apps.twitter.com](https://apps.twitter.com/)

Got all those things?  Install with:

```bash
pip install https://github.com/cnelson/substweet/archive/master.zip
```

# USAGE
```
usage: substweet [-h] [--delay DELAY] [--thread] [--num NUM] [--state STATE]
               [--ffmpeg FFMPEG]
               video [subtitles]

Post GIFs of a video with subtitles to twitter.

NOTE ON TWITTER SECRETS:

In addition to the options listed below, this program will read
on line from stdin  and expects to find the twitter secrets
required to post to an account in the following space-seperated
format:
<consumer key> <consumer secret> <access key> <access secret>

It's recommended you store these secrets in a file and then pipe it
to the program to avoid exposing secrets via the process table.

touch /tmp/secrets
chmod 600 /tmp/secrets
echo "<consumer key> <consumer secret> <access key> <access secret>" >
/tmp/secrets

substweet video.mp4 < /tmp/secrets

EXAMPLE COMMANDS:

Post as quickly as possible while avoiding rate limits:
    substweet video.mp4

The same, but in a single thread:
    substweet --thread video.mp4

Post one post every hour
    substweent --delay 3600 video.mp4

Post three posts then exit, reading prior state from a file
    substweet --num 3 --state /tmp/state.json video.mp4

Use subtitles from an external file
    substweet video.mp4 subs.srts

FAQ:

My GIFs are too short, why?

    Twitter caps GIFs at 5MB.  This program will shorten GIFs by
    removing frames to stay under this limit.  Try using a smaller
    --fps or --width/--height.

Twitter is yelling at me about rate limits, why?

    Did you set a manual --delay?  It's probably too short.

positional arguments:
  video                 The video file to post
  subtitles             The subtitles file (optional, if not specified the
                        video file must have a subtitle track)

optional arguments:
  -h, --help            show this help message and exit
  --delay DELAY         Number of seconds to sleep between posts. If not
                        specified will post as quickly as possible while
                        respecting rate limits. If set to too low of a value
                        you will exceed rate limits and the program will exit
  --thread              Post GIFs in a single thread instead of individual
                        posts
  --num NUM             Make this many posts then exit
  --state STATE         Read/write state information from this file. If state
                        information exists, continue posting from where the
                        left run of this program left off
  --ffmpeg FFMPEG, -f FFMPEG
                        The full path to ffmpeg binary (optional, if not
                        already in $PATH)
