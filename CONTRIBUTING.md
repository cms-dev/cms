# Contributing and pull request process

To contribute, please send an email to contestms-discuss@googlegroups.com, or ping us on gitter with what you plan to do (unless uncontroversial and/or small), so that we can agree on the best way to implement it.

We appreciate small commits that do one thing, but also that, when possible, each commit doesn't break the master branch. Please use your best judgement for the size of the commit according to these guidelines. If a commit breaks master, we at least require to push together all commits until master is fixed.

We also appreciate a tidy history, so after you write all your code, consider tidying up the commits to reflect what you did at the end, which is usually a simplified version of the process that you followed to reach the final state. Moreover, each commit should not have PEP 8 or pyflakes warnings (see below for how to make sure you don't introduce any).

If your change involves more than one commit, please create a PR for each of them, unless for very small and obvious commits (read: fixing typos, comments, a few obvious lines), or unless some commit breaks master.

During the review, please address all comments by creating one or more 'fixup' commits on top of the branch (no forced push). At the end, either you or one of the owners can squash appropriately the fixups.

# Code style

For Python code, we generally follow [PEP 8](https://www.python.org/dev/peps/pep-0008/).

We get around Python flexible type system in several ways:
* we try to avoid "magic" (e.g., generating or changing classes on the fly);
* we are fairly verbose with naming, trying to help the reader with following the types;
* we follow our type annotation system for method and function docstrings (planning to switch to [PEP 484](https://www.python.org/dev/peps/pep-0484/) when we will remove support for Python 2); see later for the format.

We support both Python 2 and 3, so we use the package six as required. In the medium future we will drop support to Python 2 and remove all temporary measures to support both at the same time. If you write some code that will need to be changed at that time, try to phrase it with six.

# Docstring type annotation format

We use a custom format for type annotation in method and function docstrings. Here's an example taken from the code:

```
class Cls(object):
    [...]
    def example(self, a, b, c=None):
        """Perform an example action, described here in one line.

        This is a longer description of what the method does and can
        occupy more than one line, each shorter than 80 characters.

        a (int): a is a required integer.
        b ([{str: int}]): b is a list of dictionaries mapping strings to
             integers, and note how the docstring wraps with indent.
        c (Submission|None): c is either a Submission (not required to
            fully specify, but it could be helpful for symbols that are
            not imported) or None.

        return ((int, str)): this method returns a tuple containing an
            integer and a string.

        raise (ValueError): if a is negative.
        raise (LookupError): if we could not find something.

        """
```

Note that
* everything is written with the imperative form;
* there should be an initial stand-alone first line, that can be followed by a longer description, possibly with multiple paragraphs;
* there are blank lines between: the first line, each paragraph of the longer description, the arguments section, the return section, the exceptions section, and at the end;

For very short and simple functions, you can simplify the docstring as needed (but please err on the verbosity side). If a single line, it should look like this:

```
def sqrt(x):
    """Return the square root of x."""
```
