import dayjs, { Dayjs } from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
dayjs.extend(utc);
dayjs.extend(timezone);
export const beijingInput = (value?: string | null) =>
  dayjs(value || undefined)
    .tz("Asia/Shanghai")
    .format("YYYY-MM-DDTHH:mm:ss");
export const inputDate = (value?: string | null) => dayjs(beijingInput(value));
export const inputISO = (value: Dayjs | string) =>
  dayjs
    .tz(dayjs(value).format("YYYY-MM-DD HH:mm:ss"), "Asia/Shanghai")
    .toISOString();
