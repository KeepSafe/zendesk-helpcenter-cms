zendesk-helpcenter-cms
===================

Python script for zendesk helpcenter translations.

## Requirements

1. Python 3.+
2. [WebTranslateIt](https://webtranslateit.com) APIKey
3. [Zendesk](www.zendesk.com) Account
4. [wti](https://webtranslateit.com/en/tour/external_tools) command line tool from WebTranslateIt

## Installation

1. `pip install zendesk-translator`

## Usage

Below is a description of all available commands. You can also type `zendesk-translator -h` and `zedesk-translator [command] -h` to see help message in the console.

### Configuration

In the directory you want to have your Zendesk articles type `zendesk-translator config`. You will be ask for information required by the script. the information will be saved in `.zendesk-translator.config` file. If you need to override some values just run `zendesk-translator config` again. If the file exists it will offer existing values as defaults. You can also manually create/override values in the file if you wish to do so but make sure the syntax is correct.

The current working directory is used as the root for the script. This means the categories will be created at that level.

### Importing existing articles

If you already have some articles in Zendesk you can import them with `zendesk-translator import` command.

It is possible to create the initial setup by hand but we recommend creating a sample article in Zendesk (if there are no articles there yet) and using the `import` command 

This will create a directory structure similar to the one below:

```
category/
	__group__.json
	.group.meta
	section/
		__group__.json
		.group.meta
		en-us/
			title.md
			title.json
			.article_title.meta
```

### Uploading articles to WebTranslateIt

Since we have the articles in Markdown in the main language we can now upload them to WebTranslateIt for translation. You can either use [wti](https://webtranslateit.com/en/tour/external_tools) command line tool provided by WebTranslateIt or simply run:

`python translator.py translate`

It will upload the articles to WebTranslateIt. From this point the interaction with WebTranslateIt should be done through `wti`. This includes downloading translated content, uploading new content, updating existing content and so on.

### Uploading translations to Zendesk

When the translations are ready run:

`wti pull`

This will download all translations to the local folder with existing articles. To upload everything to Zendesk run

`zendesk-translator export`

This will upload the **entire** structure to Zendesk updating whatever is already there if it changed (this is checked by comparing md5 hashes of the title and body/description)

**Important: ** 
*For uploading images use `![Alt name]($IMAGE_ROOT/images/image.png)`. The `IMAGE_ROOT` will be replaced by `image_cdn` from the configuration.

## Structure

Going back to our sample folder structure:

```
category/
	__group__.json
	.group.meta
	section/
		__group__.json
		.group.meta
		en-us/
			title.md
			title.json
			.article_title.meta
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

This file will be translated giving you variants like `__group__.fr.json` for different languages. To change category name or description simply edit this file.

The file needs to be created when you add a new category, either by hand or by running `zendesk-translator doctor`.

Once a category is in Zendesk help centre it will also have `.group.meta` file containing the information from Zendesk. This file should not be edited and is for internal use only.

### Sections

A sections is very similar to category except it holds articles. Everything else is the same.

### Articles

Each article has a separate Markdown file with the name being the article's name in the help centre (!!! this needs to change as names must be translated !!!). The content of the markdown file is the body of the article.

Once an article is in Zendesk it will also have a meta file. This file stores information from Zendesk and is for internal use by the script.

## Commands

### Creating new items

```
zendesk-translator add "path/to/article.md"
```

It will create any necessary files. It won't upload the content anywhere. If you want to upload the content to Zendesk use `export` task. If you want to upload the content to WebTranslateIt use `wti`

### Removing items

```
zendesk-translator remove  "path/to/article.md"
zendesk-translator remove "category"
```

It will remove files locally and from Zendesk and WebTranslateIt. It will not remove categories/sections together with articles even if they are empty, it has to be done separately from removing articles. Removing category/section will remove everything in it.

### Fixing missing files

If you want you can create categories/sections/articles by hand. Instead of creating all necessary files you can create folders for categories/sections and the  markdown file for the article. To create missing files run `zendesk-translator doctor`. It will create files with default names (directory/)