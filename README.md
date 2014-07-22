zendesk-helpcenter-cms
===================

Python script for zendesk helpcenter translations.

# Requirements

1. Python 3.+
2. WebTranslateIt APIKey
3. Zendesk Account
4. [wti](https://webtranslateit.com/en/tour/external_tools) command line tool from WebTranslateIt

# Installation

1. `virtualenv env`
2. `source env/bin/activate`
3. `pip install -r requirements.txt`

# Usage

## Initial setup

Assuming there already articles in the Zendesk help centre in the default language, we start by importing them to local folder:

`python translate.py import`

This will create a directory structure like:

```
root/
	category/
		__group__.json
		__group__.meta
		section/
			__group__.json
			__group__.meta
			article.md
			article.meta
```

## Uploading to WebTranslateIt

Since we have the articles in Markdown in the main language we can now upload them to WebTranslateIt for translation. You can either use [wti](https://webtranslateit.com/en/tour/external_tools) command line tool provided by WebTranslateIt or simply run:

`python translator.py translate`

It will upload the articles to WebTranslateIt. From this point the interaction with WebTranslateIt should be done through `wti`. This includes downloading translated content, uploading new content, updating existing content and so on.

## Uploading translations to Zendesk

When the translations are ready run:

`wti pull`

This will download all translations to the local folder with existing articles. To upload everything to Zendesk run

`python translator.py export`

This will upload the **entire** structure to Zendesk updating whatever is already there.

# Structure



