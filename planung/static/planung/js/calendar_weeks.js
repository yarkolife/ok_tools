(function ($) {
  $(function () {
    var $modal = $('#dayPlanModal');
    var plannedItems = [];
    
    // Parse broadcast block from settings
    const [startH, startM] = BROADCAST_START.split(':').map(Number);
    const [endH, endM] = BROADCAST_END.split(':').map(Number);
    const blockStart = startH * 3600 + startM * 60; // seconds
    const blockEnd = endH * 3600 + endM * 60; // seconds
    const maxBlockSeconds = blockEnd - blockStart;

    // Normalize duration: if value is less than 3600 (1 hour), it might be in minutes (old data)
    // Convert to seconds if needed
    function normalizeDuration(duration) {
      // If duration is less than 3600 seconds (1 hour), it might be stored in minutes
      // Check if it's a reasonable duration in minutes (e.g., less than 120 minutes = 7200 seconds)
      if (duration < 3600 && duration > 0) {
        // This could be minutes, but we need to be careful
        // If duration is between 1 and 120, it's likely minutes
        // If duration is already in seconds but less than 3600, keep it as is
        // We'll assume if it's less than 120, it's minutes (old data format)
        if (duration < 120) {
          return duration * 60; // Convert minutes to seconds
        }
      }
      return duration; // Already in seconds
    }

    // Format seconds to MM:SS
    function formatTime(seconds) {
      const normalized = normalizeDuration(seconds);
      const mins = Math.floor(normalized / 60);
      const secs = normalized % 60;
      return mins + ':' + secs.toString().padStart(2, '0');
    }

    // Convert time string HH:MM or HH:MM:SS to seconds
    function timeToSeconds(timeStr) {
      if (!timeStr) return 0;
      const parts = timeStr.split(":");
      const h = parseInt(parts[0], 10) || 0;
      const m = parseInt(parts[1], 10) || 0;
      const s = parseInt(parts[2], 10) || 0;
      return h * 3600 + m * 60 + s;
    }

    // Convert seconds to HH:MM:SS format
    function secondsToTimeString(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = seconds % 60;
      return h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0') + ':' + s.toString().padStart(2, '0');
    }

    // Convert seconds to HH:MM format (for display without seconds)
    function secondsToTimeStringShort(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      return h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0');
    }

    // Check if time has seconds in second half of minute (30-59)
    // Accepts both HH:MM:SS and seconds (number)
    function isInSecondHalf(timeStrOrSeconds) {
      if (!timeStrOrSeconds) return false;
      let seconds = 0;
      if (typeof timeStrOrSeconds === 'number') {
        seconds = timeStrOrSeconds % 60;
      } else {
        const parts = timeStrOrSeconds.split(":");
        if (parts.length >= 3) {
          seconds = parseInt(parts[2], 10) || 0;
        }
      }
      return seconds >= 30 && seconds <= 59;
    }
    
    // Convert HH:MM:SS to HH:MM for display
    function timeToDisplay(timeStr) {
      if (!timeStr) return '';
      const parts = timeStr.split(":");
      if (parts.length >= 2) {
        return parts[0] + ':' + parts[1];
      }
      return timeStr;
    }
    
    // Convert HH:MM to HH:MM:SS (add seconds if missing)
    function timeWithSeconds(timeStr, defaultSeconds = 0) {
      if (!timeStr) return '';
      const parts = timeStr.split(":");
      if (parts.length === 2) {
        return timeStr + ':' + defaultSeconds.toString().padStart(2, '0');
      }
      return timeStr;
    }
    
    // Get internal time with seconds from input element
    function getInternalTime($input) {
      const internalTime = $input.data('internal-time');
      if (internalTime) {
        return internalTime;
      }
      // Fallback: if no internal time, use display time and add :00
      const displayTime = $input.val();
      return timeWithSeconds(displayTime, 0);
    }

    function setDesiredTime($input, displayTime) {
      if (displayTime && displayTime.match(/^\d{2}:\d{2}$/)) {
        $input.data('desired-time', displayTime);
      }
    }

    function getDesiredTime($input) {
      const stored = $input.data('desired-time');
      if (stored && stored.match(/^\d{2}:\d{2}$/)) {
        return stored;
      }
      const current = $input.val();
      if (current && current.match(/^\d{2}:\d{2}$/)) {
        return current;
      }
      return '00:00';
    }

    function normalizeDisplayTime(displayTime) {
      if (!displayTime) return null;
      const parts = displayTime.split(':');
      if (parts.length !== 2) return null;
      const h = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10);
      if (isNaN(h) || isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) {
        return null;
      }
      return h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0');
    }

    function recalculateSchedule() {
      let currentEndSec = blockStart;

      $('#licenseTable tbody tr:not(.gap-row)').each(function (idx) {
        const $row = $(this);
        const $input = $row.find('.start-time-input');
        const desiredDisplay = getDesiredTime($input);
        const desiredSec = timeToSeconds(desiredDisplay + ':00');
        const startSec = Math.max(desiredSec, currentEndSec);
        const startWithSeconds = secondsToTimeString(startSec);

        $input.data('internal-time', startWithSeconds);
        $row.find('.time-with-seconds').text(startWithSeconds);

        if (isInSecondHalf(startSec)) {
          $input.css('background-color', '#fff3cd').attr('title', gettext('Video starts in second half of minute (30-59 seconds)'));
        } else {
          $input.css('background-color', '').attr('title', '');
        }

        const duration = plannedItems[idx] ? plannedItems[idx].duration : (function () {
          const durationText = $row.find('td').eq(5).text();
          if (!durationText) return 0;
          const parts = durationText.split(':').map(Number);
          if (parts.length === 2) {
            return normalizeDuration(parts[0] * 60 + parts[1]);
          }
          return 0;
        })();

        const endSec = startSec + duration;
        $row.find('.end-time').text(secondsToTimeString(endSec));

        if (plannedItems[idx]) {
          plannedItems[idx].start = startWithSeconds;
        }

        currentEndSec = endSec;
      });

      updateRemainingTime();
    }

    // Round time to nearest 0 or 5 minutes
    // If within 45 seconds after a 0/5 mark, round down to that mark
    // Otherwise round up to next 0/5 mark
    function roundToFiveMinutes(seconds) {
      const totalMinutes = Math.floor(seconds / 60);
      const remainderSeconds = seconds % 60;
      
      // Check if current minute is a 0 or 5 mark
      const isAtFiveMinuteMark = (totalMinutes % 5 === 0);
      
      // If we're at 0 or 5 minute mark and within 45 seconds
      if (isAtFiveMinuteMark && remainderSeconds <= 45) {
        // Round down to this mark (ignore the seconds)
        return totalMinutes * 60;
      }
      
      // Otherwise round UP to next 5-minute mark
      const nextFiveMinuteMark = Math.ceil((totalMinutes + 1) / 5) * 5;
      return nextFiveMinuteMark * 60;
    }

    // Calculate end time for display (with seconds)
    function calculateEndTime(startTime, durationSeconds) {
      const startSec = timeToSeconds(startTime);
      const endSec = startSec + durationSeconds;
      return secondsToTimeString(endSec);
    }

    // Display block duration on page load
    $('#blockDurationDisplay').text(formatTime(maxBlockSeconds));

    // Load weekly statistics on page load
    // (function will be called after it's defined below)

    $('.date-cell').on('click', function () {
          const iso = $(this).data('date');
          // Creating date from ISO format with UTC parsing to prevent timezone issues
          const jsDate = new Date(iso + 'T00:00:00Z');

          $('#modalDateDisplay').text(jsDate.toLocaleDateString('de-DE'));
          $('#modalWeekday').text(
              jsDate.toLocaleDateString('de-DE', { weekday: 'long' })
          );
          $('#dayPlanModal').data('isoDate', iso);

          // clear old data
          plannedItems = [];
          $('#licenseTable tbody').empty();
          $('#noteText').val('');
          updateRemainingTime();

          // --- load saved TagesPlan if exists ---
          $.get('/api/day-plan/' + iso + '/')
            .done(function (data) {
                // restore rows
                data.items.forEach(function (item) {
                    // Normalize duration for old data
                    const normalizedDuration = normalizeDuration(item.duration);
                    const endTime = calculateEndTime(item.start, normalizedDuration);
                    const licenseId = item.license_id || '';
                    const licenseLink = licenseId ? '<a href="/admin/licenses/license/' + licenseId + '/change/" target="_blank">' + item.number + '</a>' : item.number;
                    const contributionLink = licenseId ? ' <a href="/admin/contributions/contribution/?q=' + item.number + '" target="_blank" title="' + gettext('View Contributions') + '">📺</a>' : '';
                    const senderResponsible = item.sender_responsible || item.author || '';
                    // Store time with seconds internally, but display only HH:MM
                    let startTimeWithSeconds = item.start;
                    if (startTimeWithSeconds && (!startTimeWithSeconds.includes(':') || (startTimeWithSeconds.match(/:/g) || []).length === 1)) {
                      // Convert HH:MM to HH:MM:SS
                      const [h, m] = startTimeWithSeconds.split(":").map(Number);
                      startTimeWithSeconds = h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0') + ':00';
                    }
                    const startTimeDisplay = timeToDisplay(startTimeWithSeconds); // Show only HH:MM
                    const $row = $('<tr data-license-id="' + (licenseId || '') + '" data-license-number="' + item.number + '">' +
                      '<td><input type="time" class="form-control input-sm start-time-input" value="' + startTimeDisplay + '" data-internal-time="' + startTimeWithSeconds + '"><small class="time-with-seconds" style="display: block; font-size: 11px; color: #6c757d; font-weight: normal; margin-top: 2px;">' + startTimeWithSeconds + '</small></td>' +
                      '<td class="end-time">' + endTime + '</td>' +
                      '<td>' + licenseLink + contributionLink + '</td>' +
                      '<td>' + (item.title || '') + (item.subtitle ? ' – ' + item.subtitle : '') + '</td>' +
                      '<td class="sender-responsible">' + senderResponsible + '</td>' +
                      '<td>' + formatTime(normalizedDuration) + '</td>' +
                      '<td><span class="drag-handle" style="cursor:move;font-size:18px;margin-right:6px;">&#9776;</span><button class="btn btn-xs btn-danger remove-row">&times;</button></td>' +
                      '</tr>');
                    $('#licenseTable tbody').append($row);

                    const $input = $row.find('.start-time-input');
                    setDesiredTime($input, startTimeDisplay);
                    $input.data('internal-time', startTimeWithSeconds);
                    $row.find('.time-with-seconds').text(startTimeWithSeconds);

                    // Apply visual indicator if time is in second half of minute (check internal seconds)
                    const startSec = timeToSeconds(startTimeWithSeconds);
                    if (isInSecondHalf(startSec)) {
                      $row.find('.start-time-input').css('background-color', '#fff3cd').attr('title', gettext('Video starts in second half of minute (30-59 seconds)'));
                    }
                    plannedItems.push({
                      number: item.number,
                      duration: normalizedDuration,
                      title: item.title,
                      subtitle: item.subtitle,
                      sender_responsible: senderResponsible,
                      license_id: licenseId,
                      start: startTimeWithSeconds // Store with seconds
                    });
                });

                recalculateSchedule();

                $('#noteText').val(data.comment || '');
                updateRemainingTime();
            })
            .fail(function () {
                // 404 - means no plan exists yet, leave modal empty
            });

          const modal = new bootstrap.Modal(document.getElementById('dayPlanModal'));
          modal.show();
      });

    function updateRemainingTime() {
      var videoItems = [];
      var gapRows = []; // Store gap rows to remove/update them

      // Собираем все видео с временем начала и длительностью
      $('#licenseTable tbody tr').each(function () {
        const $row = $(this);
        if ($row.hasClass('gap-row')) {
          gapRows.push($row);
          return; // skip gap rows
        }
        
        const $input = $row.find('.start-time-input');
        const startStr = getInternalTime($input);
        const durationText = $row.find('td').eq(5).text(); // MM:SS format (Duration is now column 5)
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = normalizeDuration(mins * 60 + secs);
        
        if (startStr && duration) {
          const startSec = timeToSeconds(startStr);
          const endSec = startSec + duration;
          
          // Update end time display
          $row.find('.end-time').text(secondsToTimeString(endSec));
          
          videoItems.push({
            start: startSec,
            end: endSec,
            duration: duration,
            $row: $row
          });
        }
      });

      // Remove old gap rows
      gapRows.forEach(function($row) {
        $row.remove();
      });

      if (videoItems.length === 0) {
        // No videos, full block is free
        const remaining = maxBlockSeconds;
        $('#remainingTime').removeClass('text-danger').addClass('text-success')
          .text(gettext('Full available'));
        return;
      }

      // Sort by start time
      videoItems.sort(function(a, b) {
        return a.start - b.start;
      });

      // Calculate total used time and insert gap visualization
      var totalUsedTime = 0;
      var currentPos = blockStart; // start from block beginning

      for (var i = 0; i < videoItems.length; i++) {
        var item = videoItems[i];
        
        // Check if video is within broadcast block
        if (item.end <= blockStart || item.start >= blockEnd) {
          // Video is completely outside the block, skip it
          continue;
        }

        // Clamp video to block boundaries
        var videoStart = Math.max(item.start, blockStart);
        var videoEnd = Math.min(item.end, blockEnd);
        var videoInBlockDuration = videoEnd - videoStart;

        // Calculate gap before this video
        var gapStart = currentPos;
        var gapEnd = videoStart;
        var gapDuration = gapEnd - gapStart;

        if (gapDuration > 0) {
          if (gapDuration < 300) { // gap < 5 minutes (300 seconds)
            // Small gap - show in light blue
            const gapMins = Math.floor(gapDuration / 60);
            const gapSecs = gapDuration % 60;
            const gapFormatted = gapMins + ':' + gapSecs.toString().padStart(2, '0');
            
            const gapRow = '<tr class="gap-row gap-row-small">' +
              '<td colspan="2" style="text-align:center; font-weight: bold;">⬇ Gap</td>' +
              '<td colspan="5" style="text-align:center;">' + gapFormatted + ' free</td>' +
              '<td></td>' +
              '</tr>';
            
            item.$row.before(gapRow);
          } else {
            // Large gap >= 5 min - show in yellow/orange
            const gapMins = Math.floor(gapDuration / 60);
            const gapSecs = gapDuration % 60;
            const gapFormatted = gapMins + ':' + gapSecs.toString().padStart(2, '0');
            
            const gapRow = '<tr class="gap-row gap-row-large">' +
              '<td colspan="2" style="text-align:center; font-weight: bold;">⬇ Large gap</td>' +
              '<td colspan="5" style="text-align:center;">' + gapFormatted + ' free (can add video)</td>' +
              '<td></td>' +
              '</tr>';
            
            item.$row.before(gapRow);
          }
        }

        // Add video time
        totalUsedTime += videoInBlockDuration;
        currentPos = videoEnd;
      }

      // Check if any video extends beyond the block
      var hasVideoExtendingBeyondBlock = false;
      for (var i = 0; i < videoItems.length; i++) {
        if (videoItems[i].end > blockEnd && videoItems[i].start < blockEnd) {
          hasVideoExtendingBeyondBlock = true;
          break;
        }
      }

      // Check if there are any large gaps (≥5 minutes)
      var hasLargeGaps = false;
      var currentPos = blockStart;
      for (var i = 0; i < videoItems.length; i++) {
        var item = videoItems[i];
        if (item.end <= blockStart || item.start >= blockEnd) {
          continue;
        }
        
        var videoStart = Math.max(item.start, blockStart);
        var gapDuration = videoStart - currentPos;
        
        if (gapDuration >= 300) { // gap >= 5 minutes
          hasLargeGaps = true;
          break;
        }
        
        currentPos = Math.max(currentPos, Math.min(item.end, blockEnd));
      }

      // Calculate remaining time
      var remaining = maxBlockSeconds - totalUsedTime;
      const $remaining = $('#remainingTime');

      // Block is full only if: video extends beyond AND no large gaps AND remaining < 5 min
      if (hasVideoExtendingBeyondBlock && !hasLargeGaps && remaining >= 0 && remaining < 300) {
        // Block is considered full
        $remaining.removeClass('text-danger').addClass('text-success')
          .text(gettext('Block filled (video extends beyond)'));
      } else if (remaining < 0) {
        $remaining.removeClass('text-success').addClass('text-danger')
          .text(gettext('Overplanned by %(time)s!').replace('%(time)s', formatTime(-remaining)));
      } else {
        $remaining.removeClass('text-danger').addClass('text-success')
          .text(gettext('Still %(time)s free').replace('%(time)s', formatTime(remaining)));
      }
    }

    // Check if position is free (no overlaps with existing videos)
    // Allow starting at rounded time if previous video ends within 45 seconds of that mark
    function isPositionFree(startSec, durationSec, videoItems) {
      const endSec = startSec + durationSec;
      
      for (var i = 0; i < videoItems.length; i++) {
        var item = videoItems[i];
        
        // Check if new video starts exactly at a 0 or 5 minute mark
        const startMinutes = Math.floor(startSec / 60);
        const startIsRounded = (startMinutes % 5 === 0) && (startSec % 60 === 0);
        
        // If starting at rounded time, allow if previous video ends within 45 seconds before this mark
        if (startIsRounded && item.end > startSec - 45 && item.end <= startSec) {
          // Previous video ends within 45 seconds before the rounded start time - OK
          continue;
        }
        
        // Check for overlap: new video starts before existing ends AND new video ends after existing starts
        if (startSec < item.end && endSec > item.start) {
          return false; // overlap detected
        }
      }
      return true;
    }

    // Find best position for new video (fill gaps or append to end)
    function findBestPosition(videoDuration) {
      var videoItems = [];
      
      // Collect all current videos
      $('#licenseTable tbody tr:not(.gap-row)').each(function () {
        const $row = $(this);
        const $input = $row.find('.start-time-input');
        const startStr = getInternalTime($input); // Get time with seconds
        const durationText = $row.find('td').eq(5).text(); // Duration column
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = normalizeDuration(mins * 60 + secs);
        
        if (startStr && duration) {
          const startSec = timeToSeconds(startStr);
          videoItems.push({
            start: startSec,
            end: startSec + duration,
            duration: duration
          });
        }
      });

      // Sort by start time
      videoItems.sort(function(a, b) {
        return a.start - b.start;
      });

      // Try to find a gap that fits the video
      var currentPos = blockStart;
      
      for (var i = 0; i < videoItems.length; i++) {
        var item = videoItems[i];
        
        // Skip videos outside the block
        if (item.start >= blockEnd) break;
        if (item.end <= blockStart) continue;
        
        var videoStart = Math.max(item.start, blockStart);
        var gapDuration = videoStart - currentPos;
        
        // If there's a gap that fits our video (with some margin for rounding)
        if (gapDuration >= videoDuration) {
          // Try rounded position
          var roundedPos = roundToFiveMinutes(currentPos);
          
          // Check if rounded position is still free and fits in the gap
          if (roundedPos >= currentPos && 
              roundedPos + videoDuration <= videoStart && 
              isPositionFree(roundedPos, videoDuration, videoItems)) {
            return roundedPos;
          }
          
          // If rounded position doesn't work, use exact position if it fits
          if (currentPos + videoDuration <= videoStart) {
            return currentPos;
          }
        }
        
        currentPos = Math.max(currentPos, item.end);
      }
      
      // No suitable gap found, append to end
      // Round to 5 minutes, but make sure it doesn't overlap
      var roundedPos = roundToFiveMinutes(currentPos);
      
      // If rounding back would cause overlap, round forward instead
      if (roundedPos < currentPos || !isPositionFree(roundedPos, videoDuration, videoItems)) {
        // Round up to next 5-minute mark
        const totalMinutes = Math.ceil(currentPos / 60);
        const roundedMinutes = Math.ceil(totalMinutes / 5) * 5;
        roundedPos = roundedMinutes * 60;
      }
      
      return roundedPos;
    }

    $('#addLicenseBtn').on('click', function () {
      const number = $('#licenseNumberInput').val().trim();
      if (!number) return;

      $.get('/api/license/' + number + '/', function (data) {
        // Find best position for this video
        const bestPosition = findBestPosition(data.duration_seconds);
        const startTime = secondsToTimeString(bestPosition);
        const endTime = secondsToTimeString(bestPosition + data.duration_seconds);
        const licenseId = data.license_id || '';
        const licenseLink = licenseId ? '<a href="/admin/licenses/license/' + licenseId + '/change/" target="_blank">' + data.number + '</a>' : data.number;
                    const contributionLink = licenseId ? ' <a href="/admin/contributions/contribution/?q=' + data.number + '" target="_blank" title="' + gettext('View Contributions') + '">📺</a>' : '';
        const senderResponsible = data.sender_responsible || data.author || '';

        // Format start time: store with seconds internally, display only HH:MM
        const startTimeWithSeconds = startTime + ':00';
        const startTimeDisplay = timeToDisplay(startTimeWithSeconds); // Show only HH:MM
        const $row = $('<tr data-license-id="' + (licenseId || '') + '" data-license-number="' + data.number + '">' +
          '<td><input type="time" class="form-control input-sm start-time-input" value="' + startTimeDisplay + '" data-internal-time="' + startTimeWithSeconds + '"><small class="time-with-seconds" style="display: block; font-size: 11px; color: #6c757d; font-weight: normal; margin-top: 2px;">' + startTimeWithSeconds + '</small></td>' +
          '<td class="end-time">' + endTime + '</td>' +
          '<td>' + licenseLink + contributionLink + '</td>' +
          '<td>' + data.title + (data.subtitle ? ' – ' + data.subtitle : '') + '</td>' +
          '<td class="sender-responsible">' + senderResponsible + '</td>' +
          '<td>' + formatTime(data.duration_seconds) + '</td>' +
          '<td><span class="drag-handle" style="cursor:move;font-size:18px;margin-right:6px;">&#9776;</span><button class="btn btn-xs btn-danger remove-row">&times;</button></td>' +
          '</tr>');

        const $input = $row.find('.start-time-input');
        setDesiredTime($input, startTimeDisplay);
        $input.data('internal-time', startTimeWithSeconds);
        $row.find('.time-with-seconds').text(startTimeWithSeconds);

        // Find correct position to insert (sorted by time)
        var inserted = false;
        $('#licenseTable tbody tr:not(.gap-row)').each(function() {
          const $existingInput = $(this).find('.start-time-input');
          const existingStart = timeToSeconds(getInternalTime($existingInput));
          if (bestPosition < existingStart) {
            $(this).before($row);
            inserted = true;
            return false; // break
          }
        });
        
        if (!inserted) {
          $('#licenseTable tbody').append($row);
        }
        
        // Apply visual indicator if time is in second half of minute (check internal seconds)
        const startSec = timeToSeconds(startTimeWithSeconds);
        if (isInSecondHalf(startSec)) {
          $row.find('.start-time-input').css('background-color', '#fff3cd').attr('title', gettext('Video starts in second half of minute (30-59 seconds)'));
        }

        plannedItems.push({
          number: data.number,
          duration: data.duration_seconds,
          title: data.title,
          subtitle: data.subtitle,
          sender_responsible: senderResponsible,
          license_id: licenseId,
          start: startTime
        });

        recalculateSchedule();
        
        // Re-sort planned items
        syncPlannedItemsFromTable();
        updateRemainingTime();
        $('#licenseNumberInput').val('');
      }).fail(function () {
        alert(gettext('License not found or not confirmed'));
      });
    });

    // Synchronize start time when input changes (just update)
    $('#licenseTable').on('input', '.start-time-input', function () {
      const $input = $(this);
      const normalized = normalizeDisplayTime($input.val());

      if (!normalized) {
        return; // wait until input is complete HH:MM
      }

      if ($input.val() !== normalized) {
        $input.val(normalized);
      }

      setDesiredTime($input, normalized);
      recalculateSchedule();
    });

    // Validate time conflicts when user finishes editing
    $('#licenseTable').on('blur', '.start-time-input', function () {
      const $input = $(this);
      const normalized = normalizeDisplayTime($input.val());

      if (!normalized) {
        // Revert to previous desired time if current value invalid
        const fallback = getDesiredTime($input);
        $input.val(fallback);
        return;
      }

      if ($input.val() !== normalized) {
        $input.val(normalized);
      }

      setDesiredTime($input, normalized);
      recalculateSchedule();
    });

    // Align all start times to 0 or 5 minutes
    $('#alignToFiveMinutesBtn').on('click', function () {
      // Collect all videos with their current positions
      const videos = [];
      $('#licenseTable tbody tr:not(.gap-row)').each(function () {
        const $row = $(this);
        const $input = $row.find('.start-time-input');
        const startStr = getInternalTime($input); // Get time with seconds
        const durationText = $row.find('td').eq(5).text();
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = normalizeDuration(mins * 60 + secs);
        
        if (startStr) {
          const startSec = timeToSeconds(startStr);
          videos.push({
            $row: $row,
            startSec: startSec,
            duration: duration,
            originalIndex: $('#licenseTable tbody tr:not(.gap-row)').index($row)
          });
        }
      });
      
      // Sort by current start time
      videos.sort(function(a, b) {
        return a.startSec - b.startSec;
      });
      
      // Align each video to nearest 5-minute mark, avoiding conflicts
      let currentPos = blockStart;
      videos.forEach(function(video, videoIndex) {
        // Round current position to nearest 5-minute mark
        const roundedPos = roundToFiveMinutes(currentPos);
        
        // Check if rounded position would cause conflict with previous videos
        let finalPos = roundedPos;
        let hasConflict = false;
        let maxIterations = 100; // Safety limit
        let iterations = 0;
        
        do {
          hasConflict = false;
          iterations++;
          // Check against all already positioned videos
          for (let i = 0; i < videoIndex; i++) {
            const otherVideo = videos[i];
            const otherEndSec = otherVideo.finalPosSec + otherVideo.duration;
            const newEndSec = finalPos + video.duration;
            
            // Check for overlap (not touching)
            if (finalPos < otherEndSec && newEndSec > otherVideo.finalPosSec) {
              hasConflict = true;
              // Move to next 5-minute mark after the conflicting video
              const nextFiveMin = Math.ceil(otherEndSec / 300) * 300; // Round up to next 5 minutes
              finalPos = nextFiveMin;
              break;
            }
          }
        } while (hasConflict && iterations < maxIterations);
        
        // Store final position
        video.finalPosSec = finalPos;
        
        // Update the row
        const newStartTimeWithSeconds = secondsToTimeString(finalPos);
        const newStartTimeDisplay = timeToDisplay(newStartTimeWithSeconds);
        const $input = video.$row.find('.start-time-input');
        $input.val(newStartTimeDisplay); // Display only HH:MM
        $input.data('internal-time', newStartTimeWithSeconds); // Store with seconds
        setDesiredTime($input, newStartTimeDisplay);
        $input.siblings('.time-with-seconds').text(newStartTimeWithSeconds); // Update time display
        const endTime = calculateEndTime(newStartTimeWithSeconds, video.duration);
        video.$row.find('.end-time').text(endTime);
        
        // Move position forward for next video
        currentPos = finalPos + video.duration;
      });
      
      // Update plannedItems and re-sort rows by time
      syncPlannedItemsFromTable();
      
      // Re-sort table rows by new start times
      let rows = $('#licenseTable tbody tr:not(.gap-row)').get();
      rows.sort(function(a, b) {
        const $aInput = $(a).find('.start-time-input');
        const $bInput = $(b).find('.start-time-input');
        const aTime = getInternalTime($aInput);
        const bTime = getInternalTime($bInput);
        return aTime.localeCompare(bTime);
      });
      $.each(rows, function(idx, row) {
        $('#licenseTable tbody').append(row);
      });
      
      recalculateSchedule();
    });

    $('#licenseTable').on('click', '.remove-row', function () {
      const row = $(this).closest('tr');
      const index = $('#licenseTable tbody tr:not(.gap-row)').index(row);
      plannedItems.splice(index, 1);
      row.remove();
      syncPlannedItemsFromTable();
      recalculateSchedule();
    });

    function collectPlanData () {
      const isoDate = $('#dayPlanModal').data('isoDate');   // yyyy‑MM‑dd
      if (!isoDate) {
          alert("⚠️ Date is missing.");
          return null;
      }

      const items = [];

      $('#licenseTable tbody tr:not(.gap-row)').each(function (index) {
          const $row = $(this);
          const titleCell = $row.find('td').eq(3).text(); // index changed
          let title = titleCell;
          let subtitle = "";
          if (titleCell.includes(' – ')) {
            [title, subtitle] = titleCell.split(' – ', 2);
          }

          const durationText = $row.find('td').eq(5).text(); // Duration is now column 5
          const [mins, secs] = durationText.split(':').map(Number);
          const duration = normalizeDuration(mins * 60 + secs);

          // Extract license number from link or text
          const numberCell = $row.find('td').eq(2);
          let licenseNumber = numberCell.text().trim();
          // If it's a link, extract number from link text
          const linkText = numberCell.find('a').first().text();
          if (linkText) {
            licenseNumber = linkText.trim();
          }

          const $input = $row.find('.start-time-input');
          const item = {
              number:    parseInt(licenseNumber, 10),
              start:     getInternalTime($input), // Get time with seconds
              duration:  duration,
              title:     title,
              subtitle:  subtitle,
              sender_responsible: $row.find('td.sender-responsible').text(),
              license_id: $row.data('license-id') || null
          };

          items.push(item);
      });

      return {
          date: isoDate,
          items: items,
          comment: $('#noteText').val()
      };
    }

    $('#savePlanBtn').on('click', function () {
      const data = collectPlanData();
      if (!data) return;        // invalid date

      data.draft = true;

      $.ajax({
        url: '/api/day-plan/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function (response) {
          alert("Draft saved successfully.");
          location.reload(); // refresh calendar
        },
        error: function (xhr, status, error) {
          alert("Error saving the draft.");
        }
      });
    });

    $('#planPlanBtn').on('click', function () {
      const data = collectPlanData(); // no draft
      if (!data) return;        // invalid date

      data.planned = true;

      $.ajax({
        url: '/api/day-plan/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function () {
          alert("Plan saved successfully!");
          const modal = bootstrap.Modal.getInstance(document.getElementById('dayPlanModal'));
          modal.hide();
          location.reload(); // refresh calendar
        },
        error: function () {
          alert("Error saving the plan. Please try again.");
        }
      });
    });

    function getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== '') {
          const cookies = document.cookie.split(';');
          for (let i = 0; i < cookies.length; i++) {
              const cookie = cookies[i].trim();
              if (cookie.substring(0, name.length + 1) === (name + '=')) {
                  cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                  break;
              }
          }
      }
      return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    $('#dayPlanModal .btn-danger').on('click', function () {
      const isoDate = $('#dayPlanModal').data('isoDate');
      if (!isoDate) {
          alert("⚠️ Date is missing.");
          return;
      }
      if (!confirm("Delete plan for this day?")) return;

      $.ajax({
        url: '/api/day-plan/' + isoDate + '/',
        method: 'DELETE',
        beforeSend: function(xhr) {
          xhr.setRequestHeader('X-CSRFToken', csrftoken);
        },
        success: function () {
          alert("Plan deleted!");
          const modal = bootstrap.Modal.getInstance(document.getElementById('dayPlanModal'));
          modal.hide();
          location.reload(); // refresh calendar
        },
        error: function () {
          alert("Error deleting the plan.");
        }
      });
    });

    // Drag-and-drop rows (only non-gap rows)
    $('#licenseTable tbody').sortable({
      items: 'tr:not(.gap-row)',
      handle: '.drag-handle',
      update: function () {
        recalculateAllStartTimes();
        syncPlannedItemsFromTable();
        updateRemainingTime();
      }
    });

    // Time sort button
    $('#sortByTimeBtn').on('click', function () {
      let rows = $('#licenseTable tbody tr:not(.gap-row)').get();
      rows.sort(function(a, b) {
        let aTime = $(a).find('input[type="time"]').val();
        let bTime = $(b).find('input[type="time"]').val();
        return aTime.localeCompare(bTime);
      });
      $.each(rows, function(idx, row) {
        $('#licenseTable tbody').append(row);
      });
      recalculateAllStartTimes();
      syncPlannedItemsFromTable();
      updateRemainingTime();
    });

    // Synchronize plannedItems with the table
    function syncPlannedItemsFromTable() {
      plannedItems = [];
      $('#licenseTable tbody tr:not(.gap-row)').each(function () {
        const $row = $(this);
        const $input = $row.find('.start-time-input');
        const start = getInternalTime($input); // Get time with seconds
        const numberCell = $row.find('td').eq(2);
        let licenseNumber = numberCell.text().trim();
        const linkText = numberCell.find('a').first().text();
        if (linkText) {
          licenseNumber = linkText.trim();
        }
        const titleCell = $row.find('td').eq(3).text();
        let [title, subtitle] = titleCell.split(' – ', 2);
        const senderResponsible = $row.find('td.sender-responsible').text();
        const durationText = $row.find('td').eq(5).text(); // Duration is now column 5
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = normalizeDuration(mins * 60 + secs);
        plannedItems.push({ 
          start, 
          number: parseInt(licenseNumber, 10), 
          title, 
          subtitle, 
          sender_responsible: senderResponsible,
          license_id: $row.data('license-id') || null,
          duration 
        });
      });
    }

    // Recalculate start times for all videos in sequence
    function recalculateAllStartTimes() {
      var currentPos = blockStart;
      
      $('#licenseTable tbody tr:not(.gap-row)').each(function () {
        const $row = $(this);
        const durationText = $row.find('td').eq(5).text(); // Duration is now column 5
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = normalizeDuration(mins * 60 + secs);
        
        // Calculate rounded position
        const roundedPos = roundToFiveMinutes(currentPos);
        const newStartTimeWithSeconds = secondsToTimeString(roundedPos);
        const newStartTimeDisplay = timeToDisplay(newStartTimeWithSeconds);
        
        // Update start time input
        const $input = $row.find('.start-time-input');
        $input.val(newStartTimeDisplay); // Display only HH:MM
        $input.data('internal-time', newStartTimeWithSeconds); // Store with seconds
        setDesiredTime($input, newStartTimeDisplay);
        $input.siblings('.time-with-seconds').text(newStartTimeWithSeconds); // Update time display
        
        // Update end time display
        const endSec = roundedPos + duration;
        $row.find('.end-time').text(secondsToTimeString(endSec));
        
        // Move position forward
        currentPos = endSec;
      });
      
      recalculateSchedule();
    }

    // Function to load and display weekly statistics
    var loadWeeklyStatistics = function() {
      var currentWeek = parseInt(CURRENT_WEEK, 10);
      var weeks = [currentWeek, currentWeek + 1, currentWeek + 2, currentWeek + 3];

      weeks.forEach(function(weekNum, weekIndex) {
        var weekData = {
          planned: 0,
          totalTime: 0,
          freistellungen: new Set() // Уникальные номера лицензий
        };

        // Get all dates for this week
        var weekStart = getWeekStartDate(weekNum);

        // Create unique counter for this week
        var weekCounter = {
          daysProcessed: 0,
          totalDays: 7
        };

        // Load data for each day in the week
        for (var i = 0; i < 7; i++) {
          var date = new Date(weekStart);
          date.setDate(date.getDate() + i + 1);  // +1 день для сдвига
          var isoDate = date.toISOString().split('T')[0];

          // Use IIFE to create proper closure for weekIndex and counters
          (function(currentWeekIndex, currentWeekData, currentWeekCounter) {
            var apiUrl = '/api/day-plan/' + isoDate + '/';

            $.get(apiUrl)
              .done(function (data) {

                if (data.items && data.items.length > 0) {
                  currentWeekData.planned++;
                  data.items.forEach(function(item) {
                    currentWeekData.totalTime += item.duration || 0;
                    // Добавляем номер лицензии в Set для уникальности
                    if (item.number) {
                      currentWeekData.freistellungen.add(item.number);
                    }
                  });
                }

                currentWeekCounter.daysProcessed++;

                // Update statistics only when all days are processed
                if (currentWeekCounter.daysProcessed === currentWeekCounter.totalDays) {
                  updateWeekStatistics(currentWeekIndex, currentWeekData);
                }
              })
              .fail(function (xhr, status, error) {
                currentWeekCounter.daysProcessed++;

                // Update statistics even if some days failed
                if (currentWeekCounter.daysProcessed === currentWeekCounter.totalDays) {
                  updateWeekStatistics(currentWeekIndex, currentWeekData);
                }
              });
          })(weekIndex, weekData, weekCounter);
        }
      });
    };

    // Helper functions for date calculations
    var getWeekStartDate = function(weekNum) {
      // Calculate start date for given week number
      var currentYear = new Date().getFullYear();
      var jan1 = new Date(currentYear, 0, 1);
      var days = (weekNum - 1) * 7;
      var weekStart = new Date(jan1.getTime() + days * 24 * 60 * 60 * 1000);

      // Adjust to Monday
      var dayOfWeek = weekStart.getDay();
      var mondayOffset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
      weekStart.setDate(weekStart.getDate() - mondayOffset);

      return weekStart;
    };

    var getWeekEndDate = function(weekNum) {
      var weekStart = getWeekStartDate(weekNum);
      var weekEnd = new Date(weekStart);
      weekEnd.setDate(weekEnd.getDate() + 6);
      return weekEnd;
    };

    // Update statistics display for specific week
    var updateWeekStatistics = function(weekIndex, data) {
      var weekIds = ['currentWeek', 'nextWeek', 'afterNextWeek', 'threeWeeksAhead'];
      var weekId = weekIds[weekIndex];

      if (weekId) {
        var maxWeeklyTime = maxBlockSeconds * 7; // Total seconds per week
        var fillRate = Math.round((data.totalTime / maxWeeklyTime) * 100);
        
        var totalMins = Math.floor(data.totalTime / 60);
        var maxMins = Math.floor(maxWeeklyTime / 60);
        
        var timeText = data.totalTime > maxWeeklyTime ?
          (totalMins + '/' + maxMins + ' min (' + (totalMins - maxMins) + ' over)') :
          (totalMins + '/' + maxMins + ' min');

        $('#' + weekId + 'Planned').text(data.planned);
        $('#' + weekId + 'Time').text(timeText);
        $('#' + weekId + 'Fill').text(fillRate + '%');
        $('#' + weekId + 'Freistellungen').text(data.freistellungen.size);

        // Color coding for fill rate
        var fillElement = $('#' + weekId + 'Fill');
        if (fillRate > 100) {
          fillElement.removeClass('text-success text-warning').addClass('text-danger');
        } else if (fillRate > 80) {
          fillElement.removeClass('text-success text-danger').addClass('text-warning');
        } else {
          fillElement.removeClass('text-warning text-danger').addClass('text-success');
        }
      } else {
        console.error('Invalid weekIndex:', weekIndex);
      }
    };

    // Load weekly statistics after all functions are defined
    loadWeeklyStatistics();

  });
})(jQuery);
