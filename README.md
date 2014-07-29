zendesk-helpcenter-cms
===================

Python script for zendesk helpcenter translations.

## Requirements

1. Python 3.+
2. WebTranslateIt APIKey
3. Zendesk Account
4. [wti](https://webtranslateit.com/en/tour/external_tools) command line tool from WebTranslateIt

## Installation

1. `virtualenv env`
2. `source env/bin/activate`
3. `pip install -r requirements.txt`

**Important:** If you are using OSX make sure the virtuaenv uses python 3. You can force virtualenv to use python 3 by running `virtualenv --python=/opt/local/bin/python3 env` instead of `virtualenv env`

## Configuration

    cp translator.default translator.config
    
Copy the default config file with the command above to the `translator.config`, open it and enter you credentials.

## Usage

### Initial setup

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

### Uploading to WebTranslateIt

Since we have the articles in Markdown in the main language we can now upload them to WebTranslateIt for translation. You can either use [wti](https://webtranslateit.com/en/tour/external_tools) command line tool provided by WebTranslateIt or simply run:

`python translator.py translate`

It will upload the articles to WebTranslateIt. From this point the interaction with WebTranslateIt should be done through `wti`. This includes downloading translated content, uploading new content, updating existing content and so on.

### Uploading translations to Zendesk

When the translations are ready run:

`wti pull`

This will download all translations to the local folder with existing articles. To upload everything to Zendesk run

`python translator.py export`

This will upload the **entire** structure to Zendesk updating whatever is already there.

## Structure

Going back to our sample folder structure:

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

There are 3 kinds of objects: categories, sections and articles.

### Categories

A category is a top level group, it holds sections. Each category had a `__group__.json` file containing it's name and description. It is strongly recommended the name reflects the folder name for the default language unless there is some kind of encoding problem or something similar.

```
{
    "description": "testing category",
    "name": "test category"
}
```

This file will be translated giving you variants like `__group__.fr.json` for different languages. To change category name or description simply edit this file. **This file has to be created when you create a new category. You need to do it by hand**

Once a category is in Zendesk help centre it will also have `__group__.meta` file containing the information from Zendesk. This file should not be edited and is for internal use only by the script.

### Sections

A sections is very similar to category except it holds articles. Everything else is the same.

### Articles

Each article has a separate Markdown file with the name being the article's name in the help centre (!!! this needs to change as names must be translated !!!). The content of the markdown file is the body of the article.

Once an article is in Zendesk it will also have a meta file. This file stores information from Zendesk and is for internal use by the script.

## Creating new items

```
python translator.py add -p "path/to/article.md"
```

It will **only** create any missing files. It won't upload the content anywhere. If you want to upload the content to Zendesk use `export` task. If you want to upload the content to WebTranslateIt use `wti`

## Removing items

```
python translator.py remove -p "path/to/article.md"
```

It will remove files locally and from Zendesk and WebTranslateIt. It will not remove categories/sections even if empty, it has to be done manually.