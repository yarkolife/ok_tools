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

    // Format seconds to MM:SS
    function formatTime(seconds) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return mins + ':' + secs.toString().padStart(2, '0');
    }

    // Convert time string HH:MM to seconds
    function timeToSeconds(timeStr) {
      if (!timeStr) return 0;
      const [h, m] = timeStr.split(":").map(Number);
      return h * 3600 + m * 60;
    }

    // Convert seconds to HH:MM format
    function secondsToTimeString(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      return h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0');
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

    // Calculate end time for display
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
                    const endTime = calculateEndTime(item.start, item.duration);
                    const row = '<tr>' +
                      '<td><input type="time" class="form-control input-sm start-time-input" value="' + item.start + '"></td>' +
                      '<td class="end-time">' + endTime + '</td>' +
                      '<td>' + item.number + '</td>' +
                      '<td>' + (item.title || '') + (item.subtitle ? ' – ' + item.subtitle : '') + '</td>' +
                      '<td>' + (item.author || '') + '</td>' +
                      '<td>' + formatTime(item.duration) + '</td>' +
                      '<td><span class="drag-handle" style="cursor:move;font-size:18px;margin-right:6px;">&#9776;</span><button class="btn btn-xs btn-danger remove-row">&times;</button></td>' +
                      '</tr>';
                    $('#licenseTable tbody').append(row);
                    plannedItems.push({
                      number: item.number,
                      duration: item.duration,
                      title: item.title,
                      subtitle: item.subtitle,
                      author: item.author,
                      start: item.start
                    });
                });

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
        
        const startStr = $row.find('input[type="time"]').val();
        const durationText = $row.find('td').eq(5).text(); // MM:SS format (column index changed)
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = mins * 60 + secs;
        
        if (startStr && duration) {
          const [h, m] = startStr.split(":").map(Number);
          const startSec = h * 3600 + m * 60;
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
        const startStr = $row.find('input[type="time"]').val();
        const durationText = $row.find('td').eq(5).text();
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = mins * 60 + secs;
        
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

        const row = '<tr>' +
          '<td><input type="time" class="form-control input-sm start-time-input" value="' + startTime + '"></td>' +
          '<td class="end-time">' + endTime + '</td>' +
          '<td>' + data.number + '</td>' +
          '<td>' + data.title + (data.subtitle ? ' – ' + data.subtitle : '') + '</td>' +
          '<td>' + (data.author || '') + '</td>' +
          '<td>' + formatTime(data.duration_seconds) + '</td>' +
          '<td><span class="drag-handle" style="cursor:move;font-size:18px;margin-right:6px;">&#9776;</span><button class="btn btn-xs btn-danger remove-row">&times;</button></td>' +
          '</tr>';

        // Find correct position to insert (sorted by time)
        var inserted = false;
        $('#licenseTable tbody tr:not(.gap-row)').each(function() {
          const existingStart = timeToSeconds($(this).find('input[type="time"]').val());
          if (bestPosition < existingStart) {
            $(this).before(row);
            inserted = true;
            return false; // break
          }
        });
        
        if (!inserted) {
          $('#licenseTable tbody').append(row);
        }

        plannedItems.push({
          number: data.number,
          duration: data.duration_seconds,
          title: data.title,
          subtitle: data.subtitle,
          author: data.author,
          start: startTime
        });
        
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
      const $row = $(this).closest('tr');
      const index = $('#licenseTable tbody tr:not(.gap-row)').index($row);
      const newStart = $(this).val();
      
      if (plannedItems[index]) {
        plannedItems[index].start = newStart;
      }
      updateRemainingTime();
    });

    // Validate time conflicts when user finishes editing
    $('#licenseTable').on('blur', '.start-time-input', function () {
      const $input = $(this);
      const $row = $input.closest('tr');
      const index = $('#licenseTable tbody tr:not(.gap-row)').index($row);
      const newStart = $input.val();
      
      // Validate only complete time format
      if (!newStart || !newStart.match(/^\d{2}:\d{2}$/)) {
        return;
      }
      
      // Validate time conflicts
      if (plannedItems[index]) {
        const [h, m] = newStart.split(":").map(Number);
        const newStartMin = h * 60 + m;
        // Duration is in SECONDS, convert to minutes
        const currentDurationMin = Math.ceil(plannedItems[index].duration / 60);
        
        // Check all other videos for conflicts
        let hasConflict = false;
        let suggestedTime = null;
        
        $('#licenseTable tbody tr:not(.gap-row)').each(function (idx) {
          if (idx === index) return; // skip current row
          
          const $otherRow = $(this);
          const otherStart = $otherRow.find('input[type="time"]').val();
          // Duration is in SECONDS, convert to minutes
          const otherDurationMin = plannedItems[idx] ? Math.ceil(plannedItems[idx].duration / 60) : 0;
          
          if (otherStart && otherDurationMin) {
            const [oh, om] = otherStart.split(":").map(Number);
            const otherStartMin = oh * 60 + om;
            const otherEndMin = otherStartMin + otherDurationMin;
            const newEndMin = newStartMin + currentDurationMin;
            
            // Check for overlap
            if (
              (newStartMin >= otherStartMin && newStartMin < otherEndMin) ||
              (newEndMin > otherStartMin && newEndMin <= otherEndMin) ||
              (newStartMin <= otherStartMin && newEndMin >= otherEndMin)
            ) {
              hasConflict = true;
              
              // Suggest time after the conflicting video
              if (idx < index) {
                // Video is before current - suggest after it
                if (!suggestedTime || otherEndMin > suggestedTime) {
                  suggestedTime = otherEndMin;
                }
              } else {
                // Video is after current - suggest before it
                const beforeTime = otherStartMin - currentDurationMin;
                if (beforeTime >= blockStart && (!suggestedTime || beforeTime < suggestedTime)) {
                  suggestedTime = beforeTime;
                }
              }
            }
          }
        });
        
        if (hasConflict && suggestedTime !== null) {
          const suggestedTimeStr = Math.floor(suggestedTime / 60).toString().padStart(2, '0') + ':' +
                                    (suggestedTime % 60).toString().padStart(2, '0');
          
          const accept = confirm('⚠️ Zeitkonflikt!\n\n' +
                'Das Video überschneidet sich mit einem anderen.\n\n' +
                'Vorgeschlagene Startzeit: ' + suggestedTimeStr + '\n\n' +
                'OK = Zeit anwenden\nAbbrechen = selbst korrigieren');
          
          if (accept) {
            // User accepted suggestion
            $input.val(suggestedTimeStr);
            plannedItems[index].start = suggestedTimeStr;
            updateRemainingTime();
          } else {
            // User wants to fix manually - focus back
            $input.focus().select();
          }
        }
      }
    });

    $('#licenseTable').on('click', '.remove-row', function () {
      const row = $(this).closest('tr');
      const index = $('#licenseTable tbody tr:not(.gap-row)').index(row);
      plannedItems.splice(index, 1);
      row.remove();
      updateRemainingTime();
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

          const durationText = $row.find('td').eq(5).text(); // index changed
          const [mins, secs] = durationText.split(':').map(Number);
          const duration = mins * 60 + secs;

          const item = {
              number:    parseInt($row.find('td').eq(2).text(), 10), // index changed
              start:     $row.find('input[type="time"]').val(),
              duration:  duration,
              title:     title,
              subtitle:  subtitle,
              author:    $row.find('td').eq(4).text() // index changed
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
        const start = $row.find('input[type="time"]').val();
        const number = $row.find('td').eq(2).text(); // index changed
        const titleCell = $row.find('td').eq(3).text(); // index changed
        let [title, subtitle] = titleCell.split(' – ', 2);
        const author = $row.find('td').eq(4).text(); // index changed
        const durationText = $row.find('td').eq(5).text(); // index changed
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = mins * 60 + secs;
        plannedItems.push({ start, number, title, subtitle, author, duration });
      });
    }

    // Recalculate start times for all videos in sequence
    function recalculateAllStartTimes() {
      var currentPos = blockStart;
      
      $('#licenseTable tbody tr:not(.gap-row)').each(function () {
        const $row = $(this);
        const durationText = $row.find('td').eq(5).text();
        const [mins, secs] = durationText.split(':').map(Number);
        const duration = mins * 60 + secs;
        
        // Calculate rounded position
        const roundedPos = roundToFiveMinutes(currentPos);
        const newStartTime = secondsToTimeString(roundedPos);
        
        // Update start time input
        $row.find('input[type="time"]').val(newStartTime);
        
        // Update end time display
        const endSec = roundedPos + duration;
        $row.find('.end-time').text(secondsToTimeString(endSec));
        
        // Move position forward
        currentPos = endSec;
      });
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
