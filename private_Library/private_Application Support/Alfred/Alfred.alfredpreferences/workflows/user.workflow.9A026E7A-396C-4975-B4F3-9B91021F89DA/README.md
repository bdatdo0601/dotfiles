## Alfred Isengard Workflow
This is an [Alfred workflow](https://www.alfredapp.com/) designed to ease the pain brought about by interacting with [Isengard](https://w.amazon.com/index.php/AWS_IT_Security/Isengard). 
The main feature is opening Isengard federated AWS console links from Alfred spotlight, without having to ever touch the Isengard console.  

## Requirements
* [fzf](https://github.com/junegunn/fzf).
  * `brew install fzf` should work, but look through the `fzf` GitHub page for more options/troubleshooting.

## Installation

**[Click HERE to download latest workflow](https://code.amazon.com/packages/AlfredIsengard/blobs/mainline/--/AlfredIsengard.alfredworkflow?download=1)**

If you have issues with running the workflow due to permissions (something like "“alfred-isengard” cannot be opened because the developer cannot be verified."), 
you will need to permit the executable to run in your MacOS security settings. To do this, first run the workflow and receive an error, 
then go to "System Preferences > Security & Privacy". At the bottom of this tab, there should be a note that says ""alfred-isengard" was blocked from use because it is not from an identified developer.". Next to this,
there should be a button that says "Allow Anyway" which you should click. Now re-run the workflow again,
and you will not be prompted with one more warning from MacOS that says "macOS cannot verify the developer of “alfred-isengard”. Are you sure you want to open it?" which you should click "Open". 
There is an improvement to figure out how to properly sign this binary so that MacOS will trust it automatically, but for now this is the only workaround. 

See [troubleshooting](#troubleshooting) below if there are any issues during installation.

## How it works

Behind the scenes, Alfred Isengard Workflow stores a list of Isengard accounts you have access to in a local file.
Then when you run `isen ...`, the workflow will query and filter this list using [fzf](https://github.com/junegunn/fzf) 
(a command line fuzzy finder tool). Once you select the account you wish to access, the federated AWS console link for
that account and role will be opened in your browser. The local list of accounts is created when you run `isen refresh`
and lives locally at `~/.midway/isengard_accounts.txt`

## Getting Started

First run `isen refresh` in your Alfred spotlight (note it make take a several seconds to complete). 
Then run `isen <your account name>`. The Alfred spotlight should show you several accounts you are able to access.
Select one and get going. 

## Additional Features

#### Non-aws partitions
Alfred Isengard works for both aws-cn (bjs/zhy) and aws-gov (pdt) accounts. 

To add aws-cn accounts to your search, first run:

```bash
mwinit --cn
```  

then in Alfred you can run `isen refresh cn` and any aws-cn accounts you can access will now be accessible in the search.

To add aws-gov accounts to your search, first run:

```bash
mwinit --itar
```  

then in Alfred you can run `isen refresh itar` and any aws-cn accounts you can access will now be accessible in the search.

### Copy Account Id

When running the workflow, if the user presses `cmd+c` instead of enter on the account, then the account id will be copied to their clipboard.

### Copy Credentials

Copy credentials for the account by pressing SHIFT + ENTER, the credentials will be copied to your clipboard formatted as exported environment variables. eg:

```
export AWS_ACCESS_KEY_ID=REDACTED AWS_SECRET_ACCESS_KEY=REDACTED AWS_SESSION_TOKEN=REDACTED;
```

## Tips and Tricks

### Filtering Queryable Accounts

If you have access to a large number of accounts, AlfredIsengard search results may get a little messy. Since AlfredIsengard
simply searches a local file to figure out the accounts you have access to, you can modify this file to remove (or add)
any accounts you do not want to see in your results. For example, to exclude all accounts with `sister-team` in the name, 
you could run:

```
sed -i '' '/sister-team/d' ~/.midway/isengard_accounts.txt
```

## Future Improvements
* Implement a way to provide a contingent authorization token for the copy credentials feature.
* Dynamic query engines - allow for finders other than fuzzy finder to be configured by the user. 
* Remove the need to externally install fzf.
* Deep link to AWS services
* Easier installation of [build artifact version](https://code.amazon.com/packages/AlfredIsengard/releases/1.0/latest_artifact?version_set=AlfredIsengard/release&path=AlfredIsengard.alfredworkflow) of the workflow — right now it requires jumping through hoops with MacOS security to allow the workflow binary to run 

## Troubleshooting
* You may need to properly set the `FZF_PATH` to the correct location of the fzf binary on your computer. 
  This seems to be necessary for M1 mac users and could be necessary for other users who have installed `fzf` without homebrew.  
  You can get this location by running `which fzf` (if there is no `fzf` command then you need to [install it]((https://github.com/junegunn/fzf))). 
  You can set the variable in the Workflows section of the Alfred preferences. It's the `[X]` button on the top right.
* If you need additional help, reach out in the [#alfred-automation-interest](https://amzn-aws.slack.com/archives/C017Z5WCYMR) slack channel


