(function() {
  const fallbackConfig = {
    '0': { enabled: true, start: '10:00', end: '18:00', short_label: 'Mon' },
    '1': { enabled: true, start: '10:00', end: '18:00', short_label: 'Tue' },
    '2': { enabled: true, start: '10:00', end: '18:00', short_label: 'Wed' },
    '3': { enabled: true, start: '10:00', end: '18:00', short_label: 'Thu' },
    '4': { enabled: true, start: '10:00', end: '18:00', short_label: 'Fri' },
    '5': { enabled: false, start: null, end: null, short_label: 'Sat' },
    '6': { enabled: false, start: null, end: null, short_label: 'Sun' }
  };

  const runtimeConfig = typeof RENTAL_WORKING_HOURS !== 'undefined'
    ? RENTAL_WORKING_HOURS
    : window.RENTAL_WORKING_HOURS;

  const config = runtimeConfig && Object.keys(runtimeConfig).length
    ? runtimeConfig
    : fallbackConfig;

  const pad = (value) => String(value).padStart(2, '0');

  const toDateString = (value) => {
    const date = typeof value === 'string' ? new Date(`${value}T00:00:00`) : new Date(value);
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  };

  const parseTime = (value) => {
    if (!value) return null;
    const parts = value.split(':').map(Number);
    return (parts[0] * 60) + parts[1];
  };

  const formatTime = (minutes) => `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;

  const getDayConfig = (dateValue) => {
    if (!dateValue) return null;
    const date = new Date(`${dateValue}T00:00:00`);
    if (Number.isNaN(date.getTime())) return null;
    return config[String((date.getDay() + 6) % 7)] || null;
  };

  const isClosed = (dateValue) => {
    const dayConfig = getDayConfig(dateValue);
    return !dayConfig || !dayConfig.enabled || !dayConfig.start || !dayConfig.end;
  };

  const getFirstOpenDate = (fromDate) => {
    const current = new Date(fromDate);
    current.setHours(0, 0, 0, 0);
    for (let index = 0; index < 30; index += 1) {
      const dateString = toDateString(current);
      if (!isClosed(dateString)) {
        return dateString;
      }
      current.setDate(current.getDate() + 1);
    }
    return toDateString(fromDate);
  };

  const getSuggestedStartDate = () => {
    const now = new Date();
    let dateString = toDateString(now);
    const dayConfig = getDayConfig(dateString);
    if (!dayConfig || !dayConfig.enabled) {
      return getFirstOpenDate(now);
    }

    const nowMinutes = (now.getHours() * 60) + now.getMinutes();
    const closeMinutes = parseTime(dayConfig.end);
    if (closeMinutes === null || nowMinutes >= closeMinutes) {
      now.setDate(now.getDate() + 1);
      return getFirstOpenDate(now);
    }
    return dateString;
  };

  const getSuggestedStartTime = (dateValue) => {
    const dayConfig = getDayConfig(dateValue);
    if (!dayConfig || !dayConfig.enabled) return null;
    const opening = parseTime(dayConfig.start);
    const closing = parseTime(dayConfig.end);
    if (opening === null || closing === null) return null;

    const now = new Date();
    if (dateValue !== toDateString(now)) {
      return dayConfig.start;
    }

    let minutes = (now.getHours() * 60) + now.getMinutes();
    minutes = minutes % 30 === 0 ? minutes : minutes + (30 - (minutes % 30));
    minutes = Math.max(minutes, opening);
    if (minutes >= closing) {
      return null;
    }
    return formatTime(minutes);
  };

  const getNextEndTime = (dateValue, startTime) => {
    const dayConfig = getDayConfig(dateValue);
    if (!dayConfig || !dayConfig.enabled) return null;
    const closing = parseTime(dayConfig.end);
    const startMinutes = parseTime(startTime);
    if (closing === null || startMinutes === null) return null;
    return formatTime(Math.min(startMinutes + 30, closing));
  };

  const buildOptions = (dateValue, mode, startTime) => {
    const dayConfig = getDayConfig(dateValue);
    if (!dayConfig || !dayConfig.enabled) return [];
    const opening = parseTime(dayConfig.start);
    const closing = parseTime(dayConfig.end);
    if (opening === null || closing === null) return [];

    const values = [];
    if (mode === 'start') {
      for (let minutes = opening; minutes < closing; minutes += 30) {
        values.push(formatTime(minutes));
      }
      return values;
    }

    const minimum = Math.max(opening + 30, (parseTime(startTime) || opening) + 30);
    for (let minutes = minimum; minutes <= closing; minutes += 30) {
      values.push(formatTime(minutes));
    }
    return values;
  };

  const populateSelect = (select, values, fallbackValue) => {
    if (!select) return;
    const options = values.length ? values : (fallbackValue ? [fallbackValue] : []);
    select.innerHTML = options.map((value) => `<option value="${value}">${value}</option>`).join('');
  };

  const isWithinDayHours = (dateValue, timeValue, allowClosingTime) => {
    const dayConfig = getDayConfig(dateValue);
    if (!dayConfig || !dayConfig.enabled) return false;
    const opening = parseTime(dayConfig.start);
    const closing = parseTime(dayConfig.end);
    const current = parseTime(timeValue);
    if (opening === null || closing === null || current === null) return false;
    if (allowClosingTime) {
      return current >= opening && current <= closing;
    }
    return current >= opening && current < closing;
  };

  window.RentalWorkingHours = {
    config,
    getDayConfig,
    getFirstOpenDate,
    getSuggestedStartDate,
    getSuggestedStartTime,
    getNextEndTime,
    buildOptions,
    populateSelect,
    isClosed,
    isWithinDayHours,
    parseTime,
    formatTime
  };
})();
