import atexit
import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time

from colorama import init, Fore, Style

import twitter


def _run(cmd):
    """Execute a command with subprocess.run

    Args:
        cmd (list): Passed directly to subprocess.run

    Returns:
        CompletedProcess

    Raises:
        SystemExit: The command failed.
    """

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode > 0:
        print(Style.BRIGHT+Fore.WHITE+str(cmd)+Style.RESET_ALL)
        print(
            Style.BRIGHT+Fore.RED+result.stderr.decode('utf-8')+Style.RESET_ALL
        )
        raise SystemExit

    return result


def check_ffmpeg(ffmpeg):
    """Validate that we can execute ffmpeg, and that it was compiled with
    what we need

    Args:
        ffmpeg (str): The path to ffmpeg

    Rasies:
        IOError: Couldn't execute ffmpeg
        RuntimeError: ffmpeg is incorrectly configured

    Returns:
        True: ffmpeg is OK
    """
    result = _run([ffmpeg, '-version'])

    if 'enable-libass' not in result.stdout.decode('utf-8'):
        raise RuntimeError('ffmpeg must be compiled with --enable-libass')

    return True


def get_captions(filename, ffmpeg):
    """Extract captions from a given filename

    Args:
        filename (str): The filename to load captions from
        ffmpeg (str): The full path to ffmpeg

    Raises:
        IOError: Couldn't execute ffmpeg
        RuntimeError: Couldn't extract captions

    Yields:
        dict: A caption
    """
    result = _run([ffmpeg, '-i', filename, '-c:s', 'text', '-f', 'srt', '-'])

    if result.returncode != 0:
        raise RuntimeError(
            '{} does not contain a subtitle track'.format(filename)
        )

    return result.stdout


def parse_captions(captions):
    """Convert a SRT file into a datastructure

    Args:
        captions (str): The contents of an SRT file

    Yields:
        dict: a single caption
    """
    lines = captions.decode('utf-8').split('\n')

    while len(lines) > 0:
        txt = []
        try:
            num = int(lines.pop(0))
        except ValueError:
            continue

        st, et = lines.pop(0).replace(',', '.').strip().split(' --> ', 1)

        while True:
            ll = lines.pop(0).strip()
            if ll:
                txt.append(ll)
            else:
                break
        yield {
            'id': num,
            'start': st,
            'end': et,
            'text': txt
        }


def winhax(s):
    """this escaping is ridiculous on windows
    http://trac.ffmpeg.org/ticket/2166
    """
    s = s.replace('\\', '\\\\\\\\')
    s = s.replace(':\\', '\\\\:\\')
    return s


def make_gif(
    video,
    subtitles,
    start,
    end,
    ffmpeg,
    fps=10,
    width=506,
    height=-1,
    max_size=4.7e+6
):
    """Generate a GIF w/ subtitles from a video.

    Args:
        video (str): The path to the video file
        subtitles (str): The path to the subtitles file
        start (str): the start timestamp of the gif (passed to ffmpeg -ss)
        end (str): The end timestamp of the gif (passed to ffmpeg -to)
        ffmpeg (str): The path to the ffmpeg binary
        fps (int): The frames per second of the gif
        width (int): The width of the gif in pixels (-1 to autoscale)
        height (int): the height of the gif in pixels (-1 to autoscale)
        max_size (int): The maxmimum size of the gif.
          end will be reduced as neccessary to fit size

    Returns:
        bytes: The GIF
    """

    fh, tmpsrt = tempfile.mkstemp(suffix='.srt')
    os.close(fh)
    fh, tmppal = tempfile.mkstemp(suffix='.png')
    os.close(fh)

    opts = 'fps={},scale={}:{}:flags=lanczos'.format(
        fps,
        width,
        height
    )

    try:
        # chop out the part of the srt we we want
        _run([ffmpeg, '-ss', start, '-to', end, '-i', subtitles, '-y', tmpsrt])

        # generate the GIF palette
        _run([
            ffmpeg,
            '-ss', start,
            '-to', end,
            '-i', video,
            '-vf',
            'subtitles='+winhax(tmpsrt)+','+opts+',palettegen',
            '-y', tmppal
        ])

        # do the needful, cap at 5MB (twitter limit)
        result = _run([
            ffmpeg,
            '-ss', start,
            '-to', end,
            '-i', video,
            '-i', tmppal,
            '-lavfi', 'subtitles='+winhax(tmpsrt)+','+opts+' [x]; '
            '[x][1:v] paletteuse',
            '-f', 'gif',
            '-fs', '{:.0f}'.format(max_size),
            '-'
        ])

        return result.stdout
    finally:
        os.remove(tmpsrt)
        os.remove(tmppal)


def main(args, stdin):
    init()

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''
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

         This stupid app skipped part of my video, why!?

            This app only makes gifs for parts of the video
            that are subtitled. parts without subtitles will be skipped.

        ''')
    )

    parser.add_argument(
        'video',
        help='The video file to post'
    )

    parser.add_argument(
        'subtitles',
        nargs='?',
        help='The subtitles file (optional, if not specified the video file'
        ' must have a subtitle track)'
    )

    parser.add_argument(
        '--delay',
        default=None,
        type=float,
        help='Number of seconds to sleep between posts. If not specified will'
        ' post as quickly as possible while respecting rate limits. If set to'
        ' too low of a value you will exceed rate limits and the program will'
        ' exit'
    )

    parser.add_argument(
        '--thread',
        default=False,
        action='store_true',
        help='Post GIFs in a single thread instead of individual posts'
    )

    parser.add_argument(
        '--num',
        default=-1,
        type=int,
        help='Make this many posts then exit'
    )

    parser.add_argument(
        '--state',
        default=None,
        type=argparse.FileType('a+', encoding='utf-8'),
        help='Read/write state information from this file.  If state '
        'information exists, continue posting from where the left run of this'
        ' program left off'
    )

    parser.add_argument(
        '--fps',
        default=10,
        type=int,
        help='The fps of the GIFs'
    )

    parser.add_argument(
        '--width',
        default=506,
        type=int,
        help='The width of GIFs in pixels.  Set to -1 to autoscale'
    )

    parser.add_argument(
        '--height',
        default=-1,
        type=int,
        help='The height of GIFs in pixels.  Set to -1 to autoscale'
    )

    parser.add_argument(
        '--ffmpeg',
        '-f',
        default='ffmpeg',
        help='The full path to ffmpeg binary (optional, if not already in'
        ' $PATH)'
    )

    args = parser.parse_args(args)

    error = None
    try:
        if sys.stdin.isatty():
            print(
                'Enter consumer key, consumer secret, access key, and access'
                ' secret seperated by spaces:'
            )
        ck, cs, atk, ats = stdin.readline().strip().split(' ')

        # ffmpeg ok?
        check_ffmpeg(args.ffmpeg)

        # twitter ok?
        api = twitter.Api(
            consumer_key=ck,
            consumer_secret=cs,
            access_token_key=atk,
            access_token_secret=ats,
            sleep_on_rate_limit=bool(args.delay is None)
        )
        api.VerifyCredentials()

        # captions ok?
        capfile = args.video
        if args.subtitles:
            capfile = args.subtitles
        captions = get_captions(capfile, args.ffmpeg)

        fh, tmpcap = tempfile.mkstemp(suffix='.srt')
        atexit.register(lambda x: os.remove(x), tmpcap)
        os.write(fh, captions)
        os.close(fh)
    except ValueError:
        error = 'Secrets must be provided on stdin space seperated: ' \
                '<consumer key> <consumer secret> <access key> ' \
                '<access secret>'
    except OSError as exc:
        error = 'Cannot execute {}: {}'.format(args.ffmpeg, exc)
    except RuntimeError as exc:
        error = str(exc)
    except twitter.error.TwitterError as exc:
        error = 'Twitter error: {message} ({code})'.format(**exc.message[0])

    if error is not None:
        parser.error(error)
        # this will exit code 2

    skipto = None
    parent = None
    num = args.num

    # load state from disk, if asked
    if args.state is not None:
        try:
            args.state.seek(0)
            state = json.load(args.state)
            skipto = state['skip']
            if args.thread:
                parent = state['parent']
        except json.decoder.JSONDecodeError as exc:
            pass

    # post gifs
    for caption in parse_captions(captions):
        # seek to current postion if we loaded state
        if skipto is not None and caption['id'] != skipto:
            continue
        skipto = None

        if num == 0:
            break

        print(
            '{style.BRIGHT}{fore.CYAN}[{fore.WHITE}{id}: '
            '{fore.YELLOW}{start} - {end}'
            '{fore.CYAN}]\n{style.RESET_ALL}{indent}'.format(
                fore=Fore,
                style=Style,
                indent='\n'.join(['\t'+x for x in caption['text']]),
                **caption
            )
        )

        gif = make_gif(
            args.video,
            tmpcap,
            caption['start'],
            caption['end'],
            args.ffmpeg,
            fps=args.fps,
            width=args.width,
            height=args.height
        )

        # twitter library expects 'file like objects'
        # to also have these properties :|
        fh = io.BytesIO(gif)
        fh.mode = 'rb'
        fh.name = 'image.gif'

        # post to twitter
        try:
            resp = api.PostUpdate(
                '\n'.join(caption['text']),
                media=fh,
                in_reply_to_status_id=parent
            )
            if args.thread:
                parent = resp.id
            color = Fore.GREEN
            msg = 'https://twitter.com/{tweet.user.screen_name}' \
                  '/status/{tweet.id}'.format(tweet=resp)
        except twitter.error.TwitterError as exc:
            color = Fore.RED
            msg = 'Twitter error: {}'.format(exc)

        print(
            '{style.BRIGHT}{fore.CYAN}['
            '{fore.WHITE}{id}: {color}{msg}'
            '{fore.CYAN}]'.format(
                fore=Fore,
                style=Style,
                color=color,
                msg=msg,
                **caption
            )
        )

        # if we have a manual delay sleep here, if we are auto mode the call
        # to api.PostuUpdate() will sleep for us as required by rate limits
        if args.delay is not None:
            time.sleep(args.delay)

        num = num - 1

    # if asked, write our state to disk
    if args.state:
        args.state.seek(0)
        args.state.truncate()
        json.dump({'skip': caption['id'], 'parent': parent}, args.state)
        args.state.close()


def entrypoint():
    main(
        sys.argv[1:],
        sys.stdin
    )


if __name__ == '__main__':
    entrypoint()
