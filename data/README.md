# General
## Data Source
This data is obtained from the TalkBank repository. All corpus's are accessible at: 

https://talkbank.org/phon/access/index.html  

Note you may need to be logged in to TalkBank for this link to work. These scripts are to be used fairly as per the TalkBank guidelines. The data may not be used commercially (i.e. to train a ML model for commercial application). It is used for research purposes for McMaster University class off 2027, Team 22, capstone project. Permission of use has been obtained via email: "you can use the data for testing and only for training if nothing identifiable is in the system." Our team plans to abide by this in full. 

## Usage

These scripts extract audio files for children aged 4-6 from the following corpuses: 

* Penney
* PaidoEnglish
* Preston
* Cummings

# Installation and Setup

Run the following commands from the project root directory (talkbank_dataset).

## 1.1 Create a virtual environment (Windows)

``` bash
python -m venv .venv
.venv\Scripts\activate

```

## 1.2 Create a virtual environment (Linux)

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Install Chromium

``` bash
playwright install chromium
```

## 5.1 Run the main dataset build script

``` bash
python build_all_datasets.py
```

Note: The script will prompt you to authenticate with TalkBank  at the start and open a chrome browser for this. Login in and do not close the browser during the duration of the run. It should run till finish after this. Some corpuses might take a few hours since they attempt to download some large raw audio files.

In general:

* Penney, Paidologos: very quick, on the order of minutes
* Preston, Cummings: very slow, long downloads, on the order of hours

## 5.2 Alternative Build With Script Filtering 
The main dataset build script runs all of the build scripts. This one will only run for those datasets where all of the columns were obtained based on the transcript

i.e. Paidologos does not have a target IPA but has the spoken IPA and target word. Therefore, this would be excluded from this run. You probably want to use the run in 5.1. 

``` bash
python build_all_datasets.py -a
```

# Results
## Per Dataset
There will be a directory for each dataset. i.e.
* **talkbank_penney**
* **talkbank_paidologos**
* **talkbank_preston**
* **talkbank_cummings**

Each of these will contain 3 folders:
* **audio:** contains the raw audio files downloaded from talkbank
* **clips:** contains the clipped audio file for each word utterance
* **transcripts:** contains the .xml and .cha versions of all transcripts.  

Note the audio folder is just to have the source clip to crop for the clips folder. Once you are satisfied with the clips, you may delete the audio file if you wish. However be aware that if the script is re-ran, it will attempt to download all of these audio files again. 

Each dataset's directory will also contain a dataset.csv file which contains the compiled audio clips with some metadata. The main columns are:
* Session ID
* Utterance ID
* Word
* Actual IPA (This is what was spoken)
* Target IPA (This is the expected IPA)
* Clip File 

Session ID and Utterance ID indicate a unique data key for the data point

## Root Folder
**combined_dataset.csv**

This csv file has the same columns as above. It has an additional column called "data_source" which indicates which corpus the data point is from. This is added to the unique key for points in the csv. 

Unique Key: session_id, utterance_id, data_source
