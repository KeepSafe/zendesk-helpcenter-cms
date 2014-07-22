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

### Creating new category/section

To create a new category or section, simply create a folder. Inside the folder create a file called `__group__.json` with contents:

```
{
    "description": "...",
    "name": "..."
}
```

To upload the content for translation use `wti` command line tool. Once translated download the translations with `wti` and run `python translator.py export` to upload the content to Zendesk.

### Creating a new article

The process is similar to creating new category/section. In the section you want to create a new article, create a new markdown file. Upload the file for translations with `wti`. Once translated download translations with `wti pull` and upload to the help centre with `python translator.py export`.