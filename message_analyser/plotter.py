import os
import random
import operator
import numpy as np
import wordcloud as wc
import matplotlib
import emoji

# Use TkAgg when available (GUI), otherwise fall back to Agg for CLI/headless.
if not os.environ.get("MPLBACKEND"):
    try:
        import tkinter  # noqa: F401
        matplotlib.use("TkAgg")
    except Exception:
        matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import message_analyser.structure_tools as stools
from message_analyser.misc import avg, log_line, months_border

import mplcyberpunk
plt.style.use("cyberpunk")

from matplotlib.font_manager import FontProperties, fontManager
from matplotlib import ft2font


def _resolve_emoji_font():
    candidates = [
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/System/Library/Fonts/Apple Color Emoji.ttf",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "Apple Color Emoji",
        "Segoe UI Emoji",
        "Noto Color Emoji",
    ]
    for candidate in candidates:
        path = None
        if os.path.exists(candidate):
            path = candidate
        else:
            try:
                path = fontManager.findfont(
                    FontProperties(family=candidate), fallback_to_default=False
                )
            except Exception:
                path = None
        if not path or not os.path.exists(path):
            continue
        try:
            ft2font.FT2Font(path)
        except Exception:
            continue
        return FontProperties(fname=path)
    return None


_EMOJI_FONT = _resolve_emoji_font()


def _load_roboto_font(weight="Regular"):
    path = os.path.join(
        os.path.dirname(__file__),
        "Roboto",
        "static",
        f"Roboto-{weight}.ttf",
    )
    if os.path.exists(path):
        try:
            ft2font.FT2Font(path)
        except Exception:
            return None
        return FontProperties(fname=path)
    return None


_ROBOTO_FONT_MEDIUM = _load_roboto_font("Medium")
_ROBOTO_FONT_SEMIBOLD = _load_roboto_font("SemiBold")

if _ROBOTO_FONT_MEDIUM:
    try:
        font_name = _ROBOTO_FONT_MEDIUM.get_name()
        matplotlib.rcParams["font.family"] = font_name
        # Force registration to avoid findfont warnings on first use
        fontManager.addfont(_ROBOTO_FONT_MEDIUM.get_file())
        if _ROBOTO_FONT_SEMIBOLD:
            fontManager.addfont(_ROBOTO_FONT_SEMIBOLD.get_file())
    except Exception:
        pass

def _change_bar_width(ax, new_value):
    # https://stackoverflow.com/a/44542112
    for patch in ax.patches:
        current_width = patch.get_width()
        diff = current_width - new_value

        # we change the bar width
        patch.set_width(new_value)

        # we recenter the bar
        patch.set_x(patch.get_x() + diff * .5)


def _init_axes(figsize, subplot_kw=None):
    fig, ax = plt.subplots(figsize=figsize, subplot_kw=subplot_kw or {})
    _sync_axes_with_style(ax)
    return fig, ax


def _sync_axes_with_style(ax):
    fig = ax.figure
    fig.patch.set_facecolor(plt.rcParams.get("figure.facecolor"))
    ax.set_facecolor(plt.rcParams.get("axes.facecolor"))
    edge_color = plt.rcParams.get("axes.edgecolor")
    for spine in ax.spines.values():
        spine.set_color(edge_color)
    tick_color = plt.rcParams.get("xtick.color")
    ax.tick_params(axis="x", colors=tick_color)
    ax.tick_params(axis="y", colors=tick_color)
    label_color = plt.rcParams.get("axes.labelcolor")
    ax.xaxis.label.set_color(label_color)
    ax.yaxis.label.set_color(label_color)
    ax.title.set_color(plt.rcParams.get("text.color"))


def heat_map(msgs, path_to_save, seasons=False):
    messages_per_day = stools.get_messages_per_day(msgs)
    months = stools.date_months_to_str_months(stools.get_months(msgs))
    heat_calendar = {month: np.full(31, np.nan, dtype=float) for month in months}
    for day, d_msgs in messages_per_day.items():
        heat_calendar[stools.str_month(day)][day.day - 1] = len(d_msgs)

    max_day = len(max(messages_per_day.values(), key=len))
    data = np.array(list(heat_calendar.values()), dtype=float)

    fig, ax = _init_axes(figsize=(11, 8))
    cmap = mcolors.LinearSegmentedColormap.from_list("custom_simple", [(0.0, "#222946"),(0.4, "#aa4680"),(1.0, "#c32374") ])
    if hasattr(cmap, "copy"):
        cmap = cmap.copy()
    cmap.set_bad(ax.get_facecolor())

    im = ax.imshow(data, cmap=cmap, aspect="equal", interpolation="nearest",
                   vmin=0, vmax=max_day)

    ax.set_xticks(np.arange(31))
    ax.set_xticklabels(range(1, 32))
    ax.set_yticks(np.arange(len(months)))
    ax.set_yticklabels(months)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel(xlabel="Day", **label_props)
    ax.set_ylabel(ylabel="Month", **label_props)
    ax.margins(x=0)
    ax.grid(False)

    cbar = fig.colorbar(im, ax=ax, fraction=0.015, pad=0.05)
    cbar.ax.yaxis.set_tick_params(colors=plt.rcParams.get("xtick.color"))
    cbar.outline.set_edgecolor(plt.rcParams.get("axes.edgecolor"))

    if seasons:
        season_lines = [i for i, m in enumerate(months) if m.month % 3 == 0 and i != 0]
        for line in season_lines:
            ax.axhline(line - 0.5, color="C0", linewidth=1.0)

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, heat_map.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{heat_map.__name__} was created.")


def pie_messages_per_author(msgs, your_name, target_name, path_to_save):
    forwarded = len([msg for msg in msgs if msg.is_forwarded])
    msgs = list(filter(lambda msg: not msg.is_forwarded, msgs))
    your_messages_len = len([msg for msg in msgs if msg.author == your_name])
    target_messages_len = len(msgs) - your_messages_len
    data = [your_messages_len, target_messages_len, forwarded]
    labels = [f"{your_name}\n({your_messages_len})",
              f"{target_name}\n({target_messages_len})",
              f"Forwarded\n({forwarded})"]
    #explode = (.0, .0, .2)

    fig, ax = _init_axes(figsize=(8, 8), subplot_kw=dict(aspect="equal"))

    text_props = {"color": "white", "fontsize": 15}
    if _ROBOTO_FONT_SEMIBOLD:
        text_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD

    wedges, _, autotexts = ax.pie(x=data, colors=["C0", "C1", "#6062db"],
                                  autopct=lambda pct: f"{pct:.1f}%",
                                  wedgeprops={'linewidth' : 5, 'edgecolor' : ax.figure.get_facecolor()},
                                  textprops=text_props)

    # Create donut hole matching background color.
    face_color = ax.figure.get_facecolor()
    centre_circle = plt.Circle((0, 0), 0.75, facecolor=face_color, edgecolor=face_color)
    ax.add_artist(centre_circle)

    legend_kwargs = {"loc": "center", "bbox_to_anchor": (0.5, 0.0), "ncol": 3}
    #if _ROBOTO_FONT_SEMIBOLD:
    #    legend_kwargs["prop"] = _ROBOTO_FONT_SEMIBOLD
    ax.legend(wedges, labels,fontsize = '17', **legend_kwargs)

    plt.setp(autotexts, color="white", fontsize=15, weight="bold")

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, pie_messages_per_author.__name__ + ".png"), dpi=500)
    # plt.show()
    plt.close(fig)
    log_line(f"{pie_messages_per_author.__name__} was created.")


def _get_xticks(msgs, crop=True):
    start_date = msgs[0].date.date()
    xticks = []
    months_num = stools.count_months(msgs)
    if months_num > months_border:
        xlabel = "Month"
        months_ticks = stools.get_months(msgs)
        xticks_labels = stools.date_months_to_str_months(months_ticks)
        if (months_ticks[1] - start_date).days < 10 and crop:
            xticks_labels[0] = ""  # remove first short month tick for better look
        for month in months_ticks:
            xticks.append(max(0, (month - start_date).days))
            # it has max because start date is usually later than first month date.
    else:  # too short message history -> we split data by weeks, not months
        xlabel = "week"
        weeks_ticks = stools.get_weeks(msgs)
        xticks_labels = stools.date_days_to_str_days(weeks_ticks)
        if len(weeks_ticks) > 2 and (weeks_ticks[1] - start_date).days < 3 and crop:
            xticks_labels[0] = ""  # remove first short week tick for better look
        for date in weeks_ticks:
            xticks.append(max(0, (date - start_date).days))
            #  it has max because start date is usually later than first week date.

    return xticks, xticks_labels, xlabel


def _get_plot_data(msgs):
    """Gets grouped data to plot.

    Returns:
        x, y (tuple):
            x is a list of values for the x axis.
            y is a list of groups of messages (for y axis).
    """
    start_date = msgs[0].date.date()
    end_date = msgs[-1].date.date()
    xticks = []
    months_num = stools.count_months(msgs)
    if months_num > months_border:
        messages_per_month = stools.get_messages_per_month(msgs)
        months_ticks = list(messages_per_month.keys())
        for month in months_ticks:
            xticks.append(max(0, (month - start_date).days))
            # it has max because start date is usually later than first month date.
        y = list(messages_per_month.values())
    else:  # too short message history -> we split data by weeks, not months
        messages_per_week = stools.get_messages_per_week(msgs)
        days_ticks = messages_per_week.keys()
        for date in days_ticks:
            xticks.append(max(0, (date - start_date).days))
            #  it has max because start date is usually later than first week date.
        y = list(messages_per_week.values())

    # put x values at the middle of each bar (bin)
    x = [(xticks[i] + xticks[i + 1]) / 2 for i in range(1, len(xticks) - 1)]
    # except for the first and the last values
    x.insert(0, xticks[0])
    if len(y) > 1:
        x.append((xticks[-1] + (end_date - start_date).days) / 2)

    return x, y


def stackplot_non_text_messages_percentage(msgs, path_to_save):
    (x, y_total), (xticks, xticks_labels, xlabel) = _get_plot_data(msgs), _get_xticks(msgs)

    stacks = stools.get_non_text_messages_grouped(y_total)
    colors = [
        "#4e8be1",  # Light blue
        "#4f5c8e",  # Dark blue
        "#00c3cc",  # Cyan
        "#6a44a6",  # Purple
        "#a64cb0",  # Magenta
        "#9b2d9f",  # Dark purple
        "#e6248b"  # Pink
    ]
    #colors = cm.get_cmap("BuPu")(np.linspace(0, 0.9, len(stacks)))

    # Normalize values
    for i in range(len(stacks[0]["groups"])):
        total = sum(stack["groups"][i] for stack in stacks)
        for stack in stacks:
            if not total:
                stack["groups"][i] = 0
            else:
                stack["groups"][i] /= total


    labels = [stack["type"] for stack in stacks]
    plt.stackplot(x, *[stack["groups"] for stack in stacks], labels=labels,
                  colors=colors, alpha=0.85)

    plt.margins(0, 0)
    plt.xticks(xticks,rotation = 65)
    plt.yticks([i / 10 for i in range(0, 11, 2)])

    ax = plt.gca()
    _sync_axes_with_style(ax)
    ax.set_xticklabels(xticks_labels)
    ax.set_yticklabels([f"{i}%" for i in range(0, 101, 20)])
    ax.tick_params(axis='x', bottom=True, color="#A9A9A9")
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel(xlabel, **label_props)
    ax.set_ylabel("Non-text messages percentage", **label_props)

    # https://stackoverflow.com/a/4701285
    # Shrink current axis by 10%
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.9, box.height])
    # Put a legend to the right of the current axis
    legend_kwargs = {"loc": "center left", "bbox_to_anchor": (1, 0.5)}
    if _ROBOTO_FONT_SEMIBOLD:
        legend_kwargs["prop"] = _ROBOTO_FONT_SEMIBOLD

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1],**legend_kwargs)

    fig = ax.figure
    fig.set_size_inches(11, 8)

    fig.savefig(os.path.join(path_to_save, stackplot_non_text_messages_percentage.__name__ + ".png"), dpi=500)
    log_line(f"{stackplot_non_text_messages_percentage.__name__} was created.")
    plt.close(fig)


def barplot_non_text_messages(msgs, path_to_save):
    (x, y_total), (xticks, xticks_labels, xlabel) = _get_plot_data(msgs), _get_xticks(msgs, crop=False)

    bars = stools.get_non_text_messages_grouped(y_total)
    colors = [
        "#4e8be1",  # Light blue
        "#4f5c8e",  # Dark blue
        "#00c3cc",  # Cyan
        "#6a44a6",  # Purple
        "#a64cb0",  # Magenta
        "#9b2d9f",  # Dark purple
        "#e6248b"  # Pink
    ]
    #colors = cm.get_cmap("BuPu")(np.linspace(0, 0.9, len(bars)))

    fig, ax = _init_axes(figsize=(16, 8))
    positions = np.arange(len(xticks_labels))

    sum_bars = np.zeros(len(y_total))
    for bar in bars:
        sum_bars += np.array(bar["groups"])

    for i, bar in enumerate(bars[:-1]):
        bar_i = ax.bar(positions, sum_bars, label=bar["type"], color=colors[i], edgecolor="none")
        sum_bars -= np.array(bar["groups"])
        #mplcyberpunk.add_bar_gradient(bars=bar_i)

    bar_1 = ax.bar(positions, sum_bars, label=bars[-1]["type"], color=colors[-1], edgecolor="none")
    _change_bar_width(ax, 0.9)
    #mplcyberpunk.add_bar_gradient(bars=bar_1)

    ax.set_xticks(positions)
    ax.set_xticklabels(xticks_labels)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel(xlabel, **label_props)
    ax.set_ylabel("Messages count", **label_props)

    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.9, box.height])
    legend_kwargs = {"loc": "center left", "bbox_to_anchor": (1, 0.5)}
    if _ROBOTO_FONT_SEMIBOLD:
        legend_kwargs["prop"] = _ROBOTO_FONT_SEMIBOLD
    ax.legend(**legend_kwargs)

    fig.savefig(os.path.join(path_to_save, barplot_non_text_messages.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{barplot_non_text_messages.__name__} was created.")


def barplot_messages_per_day(msgs, path_to_save):
    messages_per_day_vals = list(stools.get_messages_per_day(msgs).values())

    xticks, xticks_labels, xlabel = _get_xticks(msgs)

    min_day = len(min(messages_per_day_vals, key=len))
    max_day = len(max(messages_per_day_vals, key=len))
    levels = max_day - min_day + 1 or 1
    greens = cm.get_cmap("PuRd")(np.linspace(0.3, 0.9, max(levels, 1)))
    colors = [greens[len(day) - min_day] for day in messages_per_day_vals]

    fig, ax = _init_axes(figsize=(20, 10))
    positions = np.arange(len(messages_per_day_vals))
    counts = [len(day) for day in messages_per_day_vals]
    bars = ax.bar(positions, counts, color=colors, edgecolor="none")
    mplcyberpunk.add_bar_gradient(bars=bars)

    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    _change_bar_width(ax, 1.0)
    ax.set_xlabel(xlabel, **label_props)
    ax.set_ylabel("Messages count", **label_props)
    ax.tick_params(axis='x', bottom=True, color="#A9A9A9")
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticks_labels)

    fig.savefig(os.path.join(path_to_save, barplot_messages_per_day.__name__ + ".png"), dpi=500)
    plt.close(fig)

    log_line(f"{barplot_messages_per_day.__name__} was created.")


def barplot_messages_per_minutes(msgs, path_to_save, minutes=2):
    messages_per_minutes = stools.get_messages_per_minutes(msgs, minutes)
    minute_values = list(messages_per_minutes.values())

    xticks_labels = stools.get_hours()
    xticks = [i * 60 // minutes for i in range(24)]

    min_minutes = len(min(minute_values, key=len))
    max_minutes = len(max(minute_values, key=len))
    levels = max_minutes - min_minutes + 1 or 1
    gnbu = cm.get_cmap("PuRd")(np.linspace(0.3, 0.9, max(levels, 1)))
    colors = [gnbu[len(day) - min_minutes] for day in minute_values]

    fig, ax = _init_axes(figsize=(20, 10))
    positions = np.arange(len(minute_values))
    counts = [len(day) for day in minute_values]
    bars = ax.bar(positions, counts, color=colors, edgecolor="none")

    _change_bar_width(ax, 1.0)
    mplcyberpunk.add_bar_gradient(bars=bars)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel("Hour", **label_props)
    ax.set_ylabel("Messages count", **label_props)
    ax.tick_params(axis='x', bottom=True, color="#A9A9A9")
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticks_labels)

    fig.savefig(os.path.join(path_to_save, barplot_messages_per_minutes.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{barplot_messages_per_minutes.__name__} was created.")


def barplot_words(msgs, your_name, target_name, words, topn, path_to_save):
    your_msgs = [msg for msg in msgs if msg.author == your_name]
    target_msgs = [msg for msg in msgs if msg.author == target_name]

    your_words_cnt = stools.get_words_countered(your_msgs)
    target_words_cnt = stools.get_words_countered(target_msgs)

    words.sort(key=lambda w: your_words_cnt[w] + target_words_cnt[w], reverse=True)
    selected_words = words[:topn]
    indices = np.arange(len(selected_words))
    width = 0.4

    your_counts = [your_words_cnt.get(word, 0) for word in selected_words]
    target_counts = [target_words_cnt.get(word, 0) for word in selected_words]

    fig, ax = _init_axes(figsize=(14, 8))
    bars1 = ax.bar(indices - width / 2, your_counts, width=width, label=your_name, color="C0")
    bars2 = ax.bar(indices + width / 2, target_counts, width=width, label=target_name, color="C1")
    mplcyberpunk.add_bar_gradient(bars=bars1)
    mplcyberpunk.add_bar_gradient(bars=bars2)

    ax.set_xticks(indices)
    ax.set_xticklabels(selected_words, rotation=45, ha="right")
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel("", **label_props)
    ax.set_ylabel("Messages count", **label_props)
    ax.legend(loc="upper right")


    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, barplot_words.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{barplot_words.__name__} was created.")


def barplot_emojis(msgs, your_name, target_name, topn, path_to_save):
    mc_emojis = stools.get_emoji_countered(msgs).most_common(topn)
    if not mc_emojis:
        return
    your_msgs = [msg for msg in msgs if msg.author == your_name]
    target_msgs = [msg for msg in msgs if msg.author == target_name]

    your_emojis_cnt = stools.get_emoji_countered(your_msgs)
    target_emojis_cnt = stools.get_emoji_countered(target_msgs)

    emo_labels = [e for e, _ in mc_emojis]
    indices = np.arange(len(emo_labels))
    width = 0.4

    your_counts = [your_emojis_cnt.get(e, 0) for e, _ in mc_emojis]
    target_counts = [target_emojis_cnt.get(e, 0) for e, _ in mc_emojis]

    fig, ax = _init_axes(figsize=(11, 8))
    bars1 = ax.bar(indices - width / 2, your_counts, width=width, label=your_name, color="C0")
    bars2 = ax.bar(indices + width / 2, target_counts, width=width, label=target_name, color="C1")
    mplcyberpunk.add_bar_gradient(bars=bars1)
    mplcyberpunk.add_bar_gradient(bars=bars2)

    ax.set_xticks(indices)
    if _EMOJI_FONT:
        ax.set_xticklabels(emo_labels)
        for label in ax.get_xticklabels():
            label.set_fontproperties(_EMOJI_FONT)
            label.set_rotation(0)
    else:
        fallback_labels = [emoji.demojize(e).strip(':').replace('_', ' ') for e, _ in mc_emojis]
        ax.set_xticklabels(fallback_labels, rotation=35, ha="right")
        ax.tick_params(axis='x', labelsize=10)

    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel("Emoji", **label_props)
    ax.set_ylabel("Messages count", **label_props)

    legend_kwargs = {}
    if _ROBOTO_FONT_SEMIBOLD:
        legend_kwargs["prop"] = _ROBOTO_FONT_SEMIBOLD
    ax.legend(loc="upper right", **legend_kwargs)

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, barplot_emojis.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{barplot_emojis.__name__} was created.")


def barplot_messages_per_weekday(msgs, your_name, target_name, path_to_save):
    messages_per_weekday = stools.get_messages_per_weekday(msgs)
    weekday_values = list(messages_per_weekday.values())
    labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    your_counts = [len([msg for msg in weekday if msg.author == your_name])
                   for weekday in weekday_values]
    target_counts = [len([msg for msg in weekday if msg.author == target_name])
                    for weekday in weekday_values]

    positions = np.arange(len(labels))
    width = 0.4

    fig, ax = _init_axes(figsize=(11, 8))
    bars1 = ax.bar(positions - width / 2, your_counts, width=width, label=your_name, color="C0")
    bars2 = ax.bar(positions + width / 2, target_counts, width=width, label=target_name, color="C1")
    mplcyberpunk.add_bar_gradient(bars=bars1)
    mplcyberpunk.add_bar_gradient(bars=bars2)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_ylabel("Messages count", **label_props)

    legend_kwargs = {}
    if _ROBOTO_FONT_SEMIBOLD:
        legend_kwargs["prop"] = _ROBOTO_FONT_SEMIBOLD
    ax.legend(loc="upper right", **legend_kwargs)
    ax.set_ylim([0,4000])


    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, barplot_messages_per_weekday.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{barplot_messages_per_weekday.__name__} was created.")


def distplot_messages_per_hour(msgs, path_to_save):
    data = [msg.date.hour for msg in msgs]

    counts, bins = np.histogram(data, bins=range(25))

    fig, ax = _init_axes(figsize=(11, 8))
    bars = ax.bar(bins[:-1], counts, width=np.diff(bins)*0.95, align="edge",
                  color="#c32374", edgecolor="none")
    mplcyberpunk.add_bar_gradient(bars=bars)
    ax.set_xticks(range(24))
    ax.set_xticklabels(stools.get_hours(), rotation=65)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel("Hour", **label_props)
    ax.set_ylabel("Messages count", **label_props)
    ax.margins(x=0)

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, distplot_messages_per_hour.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{distplot_messages_per_hour.__name__} was created.")


def distplot_messages_per_day(msgs, path_to_save):
    data = stools.get_messages_per_day(msgs)

    max_day_len = len(max(data.values(), key=len))
    values = [len(day) for day in data.values()]
    bins = list(range(0, max_day_len, 50)) + [max_day_len]
    if len(bins) < 2:
        bins = [0, max_day_len or 1]
    hist_counts, edges = np.histogram(values, bins=bins)



    fig, ax = _init_axes(figsize=(11, 8))
    bars = ax.bar(edges[:-1], hist_counts, width=np.diff(edges)*0.95, align="edge",
                  color="#c32374", edgecolor="none")
    mplcyberpunk.add_bar_gradient(bars=bars)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel("Messages count", **label_props)
    ax.set_ylabel("Number of days", **label_props)
    ax.margins(x=0)

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, distplot_messages_per_day.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{distplot_messages_per_day.__name__} was created.")


def distplot_messages_per_month(msgs, path_to_save):
    start_date = msgs[0].date.date()
    (xticks, xticks_labels, xlabel) = _get_xticks(msgs)

    bins = xticks + [(msgs[-1].date.date() - start_date).days]
    data = [(msg.date.date() - start_date).days for msg in msgs]

    hist_counts, _ = np.histogram(data, bins=bins)

    fig, ax = _init_axes(figsize=(11, 8))
    bars = ax.bar(bins[:-1], hist_counts, width=np.diff(bins)*0.95, align="edge",
                  color="#c32374", edgecolor="none")
    mplcyberpunk.add_bar_gradient(bars=bars)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticks_labels)
    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel(xlabel, **label_props)
    ax.set_ylabel("Messages count", **label_props)
    ax.margins(x=0)

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, distplot_messages_per_month.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{distplot_messages_per_month.__name__} was created.")


def lineplot_message_length(msgs, your_name, target_name, path_to_save):
    (x, y_total), (xticks, xticks_labels, xlabel) = _get_plot_data(msgs), _get_xticks(msgs)

    y_your = [avg([len(msg.text) for msg in period if msg.author == your_name]) for period in y_total]
    y_target = [avg([len(msg.text) for msg in period if msg.author == target_name]) for period in y_total]

    fig, ax = _init_axes(figsize=(13, 7))
    #ax.fill_between(x, y_your, alpha=0.3, color="C0")
    line_you, = ax.plot(x, y_your, linewidth=2.5, color="C0")
    #ax.fill_between(x, y_target, alpha=0.3, color="C1")
    line_target, = ax.plot(x, y_target, linewidth=2.5, color="C1")
    mplcyberpunk.make_lines_glow()
    mplcyberpunk.add_gradient_fill(alpha_gradientglow=0.5)

    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel(xlabel, **label_props)
    ax.set_ylabel("Average message length (characters)", **label_props)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticks_labels)
    ax.tick_params(axis='x', bottom=True, color="#A9A9A9")
    ax.margins(x=0, y=0)
    ax.legend([line_you, line_target], [your_name, target_name], prop=_ROBOTO_FONT_SEMIBOLD, loc ="upper center")

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, lineplot_message_length.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{lineplot_message_length.__name__} was created.")


def lineplot_messages(msgs, your_name, target_name, path_to_save):
    (x, y_total), (xticks, xticks_labels, xlabel) = _get_plot_data(msgs), _get_xticks(msgs)

    y_your = [len([msg for msg in period if msg.author == your_name]) for period in y_total]
    y_target = [len([msg for msg in period if msg.author == target_name]) for period in y_total]

    fig, ax = _init_axes(figsize=(13, 7))
    #ax.fill_between(x, y_your, alpha=0.3, color="C0")
    line_you, = ax.plot(x, y_your, linewidth=2.5, color="C0")
    #ax.fill_between(x, y_target, alpha=0.3, color="C1")
    line_target, = ax.plot(x, y_target, linewidth=2.5, color="C1")
    mplcyberpunk.make_lines_glow()
    mplcyberpunk.add_gradient_fill(alpha_gradientglow=0.5)

    label_props = {}
    if _ROBOTO_FONT_SEMIBOLD:
        label_props["fontproperties"] = _ROBOTO_FONT_SEMIBOLD
    ax.set_xlabel(xlabel, **label_props)
    ax.set_ylabel("Messages count", **label_props)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticks_labels)
    ax.tick_params(axis='x', bottom=True, color="#A9A9A9")
    ax.margins(x=0, y=0)
    ax.legend([line_you, line_target], [your_name, target_name],prop=_ROBOTO_FONT_SEMIBOLD, loc ="upper center")

    fig.tight_layout()
    fig.savefig(os.path.join(path_to_save, lineplot_messages.__name__ + ".png"), dpi=500)
    plt.close(fig)
    log_line(f"{lineplot_messages.__name__} was created.")


def wordcloud(msgs, words, path_to_save):
    all_words_list = []
    words_cnt = stools.get_words_countered(msgs)
    # we need to create a huge string which contains each word as many times as it encounters in messages.
    for word in set(words):
        all_words_list.extend([word] * (words_cnt[word]))
    random.shuffle(all_words_list, random.random)  # don't forget to shuffle !

    if not all_words_list:
        log_line("No such words were found in message history.")
        return

    all_words_string = ' '.join(all_words_list)

    # the cloud will be a circle.
    radius = 500
    x, y = np.ogrid[:2 * radius, :2 * radius]
    mask = (x - radius) ** 2 + (y - radius) ** 2 > radius ** 2
    mask = 255 * mask.astype(int)

    word_cloud = wc.WordCloud(background_color="white", repeat=False, mask=mask)
    word_cloud.generate(all_words_string)

    plt.axis("off")
    plt.imshow(word_cloud, interpolation="bilinear")

    word_cloud.to_file(os.path.join(path_to_save, wordcloud.__name__ + ".png"))
    # plt.show()
    plt.close()
    log_line(f"{wordcloud.__name__} was created.")
