from __future__ import annotations
import src
import rospy
from pathlib import Path
import rosbag
import matplotlib.pyplot as plt
import scienceplots
from multiprocessing import Pool
from dataclasses import dataclass, field

@dataclass
class PlotSettings:
    rosbag_path: Path
    topics: list[str]
    label_map: dict[str, str]
    outpath: Path
    slip_regions: list[tuple[float, float]] = field(default_factory=list)
    graph_range: tuple[float, float] = (0.0, 1.0)
    legend_loc: str = "best"

def plot_topics(settings: PlotSettings) -> None:
    topics = settings.label_map.keys()
    plt.style.use(['ieee', 'grid'])
    # plt.rcParams['font.serif'] = ['Times New Roman']

    bag = rosbag.Bag(str(settings.rosbag_path))
    topic_data = {topic: [] for topic in topics}
    time_data = {topic: [] for topic in topics}
    t_zero = None

    for topic, msg, t in bag.read_messages(topics=topics):
        if t_zero is None:
            t_zero = t.to_sec()
        value = getattr(msg, 'data', None)
        dt = t.to_sec() - t_zero
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            topic_data[topic].append(list(value))
        else:
            topic_data[topic].append(value)
        time_data[topic].append(dt)
    
    if not any(topic_data[topic] for topic in topics):
        print(f"No numeric data found in topics {topics} of bag {settings.rosbag_path.name}.")

    bag.close()

    plt.figure(figsize=(5, 3))
    for topic in topics:
        topic_label = settings.label_map[topic] if topic in settings.label_map else topic
        if topic_data[topic]:
            if isinstance(topic_data[topic][0], (list, tuple)):
                arr = topic_data[topic]
                arr = [list(a) for a in arr]
                arr = list(zip(*arr))
                labels = [f"[{i}]" for i in range(len(arr))]
                for i, dim in enumerate(arr):
                    plt.plot(time_data[topic], dim, label=f"{topic_label} {labels[i]}")
            else:
                plt.plot(time_data[topic], topic_data[topic], label=topic_label)
    
    # draw an opaque red rectangle for slip regions
    for i, slip_region in enumerate(settings.slip_regions):
        label = None
        if i == 0:
            label = 'Slip Regions' if len(settings.slip_regions) > 1 else 'Slip Region'
        plt.axvspan(slip_region[0], slip_region[1], color='red', alpha=0.3, label=label)
    
    plt.xlabel("Time [s]")
    plt.xlim(settings.graph_range)
    plt.ylabel("Value")
    plt.legend(loc=settings.legend_loc if settings.legend_loc else 'best')
    plt.tight_layout()
    plt.savefig(settings.outpath)
    plt.close()

def process_bag(settings: PlotSettings) -> None:
    try:
        with rosbag.Bag(str(settings.rosbag_path)) as bag:
            if bag.get_message_count() == 0:
                print(f"Skipping empty bag file: {settings.rosbag_path.name}")
                return
        print(f"Processing {settings.rosbag_path.name}")
        plot_topics(settings)
    except rosbag.bag.ROSBagException:
        print(f"Skipping invalid/corrupted bag file: {settings.rosbag_path.name}")

def main() -> None:
    (Path(src.__file__).parent.parent / "images").mkdir(exist_ok=True)
    # remove contentant of images directory
    for img_file in (Path(src.__file__).parent.parent / "images").glob("*.png"):
        img_file.unlink()

    data_dir = Path(src.__file__).parent.parent / "data"
    rosbags = list(data_dir.glob("*.bag"))

    label_map = {
        "/contact_estimation/leg1_contact": "Leg 1 Contact",
        "/contact_estimation/leg2_contact": "Leg 2 Contact",
    }
    settings_list = [
        PlotSettings(
            rosbag_path=rosbag_,
            topics=list(label_map.keys()),
            label_map=label_map,
            outpath=Path(src.__file__).parent.parent / "images" / f"{rosbag_.stem}.png",
            slip_regions=[(0.0, 1.0), (2.0, 3.0)],  # Example slip regions
            graph_range=(0, 5)  # Example graph range
        )
        for rosbag_ in rosbags
    ]

    with Pool() as pool:
        pool.map(process_bag, settings_list)

if __name__ == "__main__":
    main()