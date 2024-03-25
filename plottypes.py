"""
Infrastructure for plot.py:
- Helper classes for groupwise plots: data subsets handling
- Parameterized plotting routines
"""
import math
import os
import traceback
import typing as tg

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


class Subset(dict):
    def __getattr__(self, attrname):
        """subset dictionary keys become Python pseudo attributes"""
        return self[attrname]


class Rows(Subset):
    def rows_(self, df: pd.DataFrame) -> pd.Series:
        return self['rows'](df)

    def check_validity(self):
        if not callable(self.get('rows', False)):
            raise TypeError(f"Rows({self}) is missing essential callable 'rows'")


class Values(Subset):
    def values_(self, df: pd.DataFrame) -> tg.Any:
        return self['values'](df)

    def check_validity(self):
        if not callable(self.get('values', False)):
            raise TypeError(f"Values({self}) is missing essential callable 'values'")


class Subsets(list):
    """
    Define and handle overlapping subsets of something, e.g. rows in pd.Dataframes.
    A list of either Rows or Values objects, e.g.:
      ss = Subsets([Rows(rows=lambda df: df.a >= 0, color='red', label="A"),
                    Rows(rows=lambda df: df.b <= 0, color='blue', label="B")])
    If you initialize it all at once, like above, the consistency will be checked.
    Then iterate over groups and retrieve their rows and other attributes, e.g.
      for subset in ss:
          somecall(subset['color'], subset.rows(df).somecolumn.mean())
    """

    def __init__(self, descriptor: tg.Union[tg.Iterable[Rows], tg.Iterable[Values]]):
        super().__init__(descriptor)
        some_subset = self[0]
        some_subset.check_validity()
        the_attrs = set(some_subset.keys())
        # ----- check attributes consistency:
        for idx, descr in enumerate(self):
            descr_attrs = set(descr.keys())
            if descr_attrs > the_attrs:
                raise ValueError(f"subset {idx} has extra attributes: %s" %
                                 (descr_attrs - the_attrs))
            if the_attrs > descr_attrs:
                raise ValueError(f"subset {idx} has attributes missing: %s" %
                                 (the_attrs - descr_attrs))


class PlotContext:
    """Configuration object to supply to generic plotting operations."""
    outputdir: str
    basename: str
    df: pd.DataFrame
    subsets: tg.Optional[Subsets] = None
    inner_subsets: tg.Optional[Subsets] = None
    fig: tg.Optional[mpl.figure.Figure] = None
    ax: tg.Optional[mpl.axes.Axes] = None

    def __init__(self, outputdir, basename, df, height, width,
                 subsets=None, inner_subsets=None):
        self.outputdir = outputdir
        self.basename = basename
        self.df = df
        self.subsets = subsets
        self.inner_subsets = inner_subsets
        mpl.rcParams.update({'font.size': 8})
        figsize = (width, height)
        self.fig = mpl.figure.Figure(figsize=figsize, layout='constrained')
        self.ax = self.fig.add_subplot()

    def savefig(self):
        self.fig.savefig(os.path.join(self.outputdir, self.basename + '.pdf'))

    def again_for(self, basename: str):
        """Reuse for another plot: Clear Figure, set a different filename, else the same."""
        self.fig.clear()
        self.ax = self.fig.add_subplot()
        self.basename = basename


AddXletOp = tg.Callable[[PlotContext, float, tg.Any, Subset], None]


def plot_xletgroups(ctx: PlotContext, add_op: AddXletOp, plottype: str, basename: str, 
                    ylabel: str, *, ymax=None):
    """Draw groups of xlets (one per inner_subset) for all subsets."""
    ctx.again_for(f"{plottype}_xletgroups_{basename}")
    ctx.ax.set_ylim(bottom=0, top=ymax)
    ctx.ax.set_ylabel(ylabel)
    ctx.ax.grid(axis='y', linewidth=0.1)
    inner_x_min = min((sub['x'] for sub in ctx.inner_subsets))
    inner_x_max = max((sub['x'] for sub in ctx.inner_subsets))
    inner_width = inner_x_max - inner_x_min
    xticks = []
    for subset in ctx.subsets:
        x = (subset['x'] * inner_width * 1.25)
        xticks.append(x)
        add_xletgroup(ctx, x - inner_width/2, add_op, subset)
    ctx.ax.set_xticks(ticks=xticks, labels=[ss['label'] for ss in ctx.subsets])
    ctx.savefig()


def add_xletgroup(ctx: PlotContext, x: float, add_xlet_op: AddXletOp, subset: Subset):
    for inner_subset in ctx.inner_subsets:
        rows = subset if isinstance(subset, Rows) else inner_subset
        values = subset if isinstance(subset, Values) else inner_subset
        rows_data: pd.Series = rows.rows_(ctx.df)
        assert isinstance(rows_data, pd.Series), type(rows_data)
        xlet_data = values.values_(ctx.df[rows_data.values])
        add_xlet_op(ctx, x, xlet_data, inner_subset)


def add_boxplotlet(ctx: PlotContext, x: float,
                   xlet_data: tg.Any, inner_subset: Subset):
    color = inner_subset.get('color', "mediumblue")
    xlet_x = x + inner_subset['x']
    ctx.ax.boxplot(
        [xlet_data[xlet_data.notna()]],
        notch=False, whis=(10, 90),
        positions=[xlet_x], labels=[""],  # labels are per-group only
        widths=0.8, capwidths=0.2,
        showfliers=False, showmeans=True,
        patch_artist=True, boxprops=dict(facecolor=color),
        medianprops=dict(color='grey'),
        meanprops=dict(marker="o", markersize=3,
                       markerfacecolor="orange", markeredgecolor="orange"))


def add_nonzerofractionbarplotlet(ctx: PlotContext, x: float, xlet_data: tg.Any, inner_subset: Subset):
    """One bar that shows what fraction (in percent) of the data is nonzero"""
    color = inner_subset.get('color', "mediumblue")
    xlet_x = x + inner_subset['x']
    y = 100 * ((xlet_data != 0).sum() / len(xlet_data))
    ctx.ax.bar(x=xlet_x, height=y, width=0.8, label="", color=color)


def add_zerofractionbarplotlet(ctx: PlotContext, x: float, xlet_data: tg.Any, inner_subset: Subset):
    """One bar that shows what fraction (in percent) of the data is zero"""
    color = inner_subset.get('color', "mediumblue")
    xlet_x = x + inner_subset['x']
    y = 100 * ((xlet_data == 0).sum() / len(xlet_data))
    ctx.ax.bar(x=xlet_x, height=y, width=0.8, label="", color=color)


def plot_boxplots(ctx: PlotContext, which: str, *, ymax=None):
    """Make a plot with one boxplot for each subset."""
    ctx.again_for(f"boxplots_{which}")
    ctx.ax.set_ylim(bottom=0, top=ymax)
    ctx.ax.set_ylabel(which)
    ctx.ax.grid(axis='y', linewidth=0.1)
    for descriptor in ctx.subsets:
        vals = ctx.df.loc[descriptor.rows_(ctx.df), which]
        add_boxplot(ctx, vals, descriptor)
    ctx.savefig()


def add_boxplot(ctx, vals, descr):
    """Insert a single boxplot into a larger plot."""
    ctx.ax.boxplot(
        [vals],
        notch=False, whis=(10, 90),
        positions=[descr['x']], labels=[descr['label']],
        widths=0.7, capwidths=0.2,
        showfliers=False, showmeans=True,
        patch_artist=True, boxprops=dict(facecolor="yellow"),
        medianprops=dict(color='black'),
        meanprops=dict(marker="o", markerfacecolor="mediumblue", markeredgecolor="mediumblue"))
    # ----- add "n=123" at the bottom:
    ctx.ax.text(descr.x, 0, "n=%d" % len(vals),
                verticalalignment='bottom', horizontalalignment='center', color="mediumblue",
                fontsize=7)
    # ----- add error bar for the mean:
    mymean = vals.mean()
    se = vals.std() / math.sqrt(len(vals))  # standard error of the mean
    plt.vlines(descr.x + 0.1, mymean - se, mymean + se,
               colors='red', linestyles='solid', linewidth=0.7)


def plot_lowess(x: pd.Series, xlabel: str, y: pd.Series, ylabel: str,
                outputdir: str, name_suffix: str, *, 
                frac=0.67, show=True, xmax=None, ymax=None):
    """Plot a scatter plot plus a local linear regression line."""
    # ----- compute lowess line:
    import statsmodels.nonparametric.smoothers_lowess as sml
    delta = 0.01 * (x.max() - x.min())
    line_xy = sml.lowess(y.to_numpy(), x.to_numpy(), frac=frac, delta=delta,
                         is_sorted=False)
    # ----- plot labeling:
    plt.figure()
    plt.xlim(left=0, right=xmax)
    plt.xlabel(xlabel)
    plt.ylim(bottom=0, top=ymax)
    plt.ylabel(ylabel)
    plt.grid(axis='both', linewidth=0.1)
    # ----- plot points:
    if show:
        plt.scatter(x, y, s=2, c="darkred")
    # ----- plot lowess line:
    # print(line_xy)
    plt.plot(line_xy[:, 0], line_xy[:, 1], )
    # ----- save:
    plt.savefig(plotfilename(outputdir, name_suffix=name_suffix))


def funcname(levels_up: int) -> str:
    """The name of the function levels_up levels further up on the stack"""
    return traceback.extract_stack(limit=levels_up+1)[0].name


def plotfilename(outputdir: str, name_suffix="", nesting=0) -> str:
    """Filename derived from function name nesting+2 stackframes up."""
    if name_suffix:
        name_suffix = "_" + name_suffix
    return "%s/%s%s.pdf" % (outputdir, funcname(2+nesting).replace('plot_', ''), name_suffix)
