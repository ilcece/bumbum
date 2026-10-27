import { useId, useRef, useState } from "react";
import type { TapStats } from "./api";

export function TapDailyChart({
  daily,
  today,
}: {
  daily: TapStats["daily"];
  today: string;
}) {
  const id = useId();
  const scroll = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [focused, setFocused] = useState(false);
  const [position, setPosition] = useState(0);
  const index = Math.min(hover ?? position, Math.max(0, daily.length - 1));
  const point = daily[index];
  const maximum = daily.reduce(
    (value, entry) => Math.max(value, entry.valid_taps),
    1,
  );
  const width = Math.max(640, daily.length * 12 + 60);
  const step = (width - 60) / Math.max(1, daily.length);
  const selected = point && (hover !== null || focused);
  const dateText = (date: string) =>
    new Date(date + "T00:00:00+08:00").toLocaleDateString("zh-CN", {
      timeZone: "Asia/Shanghai",
      weekday: "long",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  function move(next: number) {
    const value = Math.max(0, Math.min(daily.length - 1, next));
    setHover(null);
    setPosition(value);
    const container = scroll.current;
    if (container) {
      const x = 40 + step * value;
      container.scrollLeft = Math.max(0, x - container.clientWidth / 2);
    }
  }
  return (
    <section className="tap-chart" aria-label="每日触碰趋势">
      <h3>每日有效触碰次数</h3>
      {!daily.some((entry) => entry.valid_taps > 0) && (
        <p className="muted-text">所选时间暂无有效触碰记录</p>
      )}
      {daily.length > 0 && (
        <>
          <p
            className="tap-chart-readout"
            id={`${id}-value`}
            role={selected ? "tooltip" : undefined}
          >
            {selected
              ? `${dateText(point.date)}：${point.valid_taps.toLocaleString("zh-CN")}次${point.date === today ? "（今日未结束）" : ""}`
              : "悬浮查看每日次数；键盘聚焦图表后，用左右键切换日期。"}
          </p>
          <div
            className="tap-chart-scroll"
            ref={scroll}
            tabIndex={0}
            role="group"
            aria-label="每日有效触碰柱状图"
            aria-describedby={`${id}-value`}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(event) => {
              if (
                ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
              ) {
                event.preventDefault();
                move(
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? daily.length - 1
                      : position + (event.key === "ArrowRight" ? 1 : -1),
                );
              }
            }}
          >
            <svg
              width={width}
              height={240}
              viewBox={`0 0 ${width} 240`}
              aria-label="每日次数，日期明细见图表提示"
              role="img"
            >
              <line
                x1={40}
                y1={200}
                x2={width - 20}
                y2={200}
                className="tap-chart-axis"
              />
              <text x={4} y={24}>
                {maximum.toLocaleString("zh-CN")}
              </text>
              <text x={20} y={204}>
                0
              </text>
              {daily.map((entry, offset) => {
                const x = 40 + offset * step;
                const height = (entry.valid_taps / maximum) * 170;
                const showLabel =
                  offset % Math.max(1, Math.ceil(daily.length / 8)) === 0 ||
                  offset === daily.length - 1;
                return (
                  <g key={entry.date}>
                    <rect
                      x={x + step * 0.2}
                      y={200 - height}
                      width={step * 0.6}
                      height={height}
                      className={
                        selected && index === offset
                          ? "tap-chart-bar selected"
                          : "tap-chart-bar"
                      }
                    />
                    <rect
                      x={x}
                      y={20}
                      width={step}
                      height={182}
                      fill="transparent"
                      onMouseEnter={() => setHover(offset)}
                      onMouseLeave={() => setHover(null)}
                    />
                    {showLabel && (
                      <text x={x + step / 2} y={225} textAnchor="middle">
                        {entry.date.slice(5)}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
          {daily.length > 45 && (
            <p className="muted-text">
              可横向滚动查看全部日期；未省略早期记录。
            </p>
          )}
        </>
      )}
    </section>
  );
}
