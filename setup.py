from setuptools import setup, find_packages

setup(
    name='substweet',
    version='0.0.1',
    description='Post GIFs of a video with subtitles to twitter.',
    url='https://github.com/cnelson/substweet',
    author='Chris Nelson',
    author_email='cnelson@cnelson.org',
    license='License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
    keywords='twitter ffmpeg gif shitpost',
    packages=find_packages(),
    install_requires=[
        'colorama',
        'python-twitter'
    ],

    entry_points={
        'console_scripts': [
            'substweet = substweet.prog:entrypoint'
        ]
    }
)
