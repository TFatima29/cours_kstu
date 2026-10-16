// Ф-8. Отметка о просмотре урока после 90% видео.
// Работает с загруженным файлом (<video>) и с YouTube (IFrame API).
(function () {
  var box = document.getElementById("lesson-player");
  if (!box) return;

  var watchedUrl = box.dataset.watchedUrl;
  var ratio = parseFloat(box.dataset.ratio || "0.9");
  var alreadyWatched = box.dataset.watched === "true";
  var csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
  var status = document.getElementById("watch-status");
  var bar = status ? status.querySelector(".progress > span") : null;
  var label = status ? status.querySelector("[data-label]") : null;
  var sent = alreadyWatched;
  var maxSeen = 0;

  function showProgress(fraction) {
    if (sent || !bar) return;
    var pct = Math.min(100, Math.round((fraction / ratio) * 100));
    bar.style.width = pct + "%";
    if (label) label.textContent = "Просмотрено " + Math.round(fraction * 100) + "%. Урок засчитается после 90%.";
  }

  function markWatched() {
    if (sent) return;
    sent = true;
    fetch(watchedUrl, {
      method: "POST",
      headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { sent = false; return; }
        if (status) {
          status.classList.add("done");
          status.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M5 12l5 5L20 7"/></svg> Урок просмотрен';
        }
        var stop = document.querySelector('.stop[aria-current="page"]');
        if (stop) stop.classList.add("watched");
        var pct = document.querySelectorAll("[data-course-percent]");
        pct.forEach(function (el) {
          if (el.tagName === "SPAN") el.style.width = data.percent + "%";
          else el.textContent = data.percent + "%";
        });
        if (data.course_completed || data.quiz_available) {
          window.setTimeout(function () { window.location.reload(); }, 900);
        }
      })
      .catch(function () { sent = false; });
  }

  function check(current, duration) {
    if (!duration || !isFinite(duration)) return;
    // учитываем самую дальнюю реально просмотренную точку, без «перемотки в конец»
    if (current <= maxSeen + 2) maxSeen = Math.max(maxSeen, current);
    var fraction = maxSeen / duration;
    showProgress(fraction);
    if (fraction >= ratio) markWatched();
  }

  var video = box.querySelector("video");
  if (video) {
    video.addEventListener("timeupdate", function () { check(video.currentTime, video.duration); });
    video.addEventListener("ended", function () { maxSeen = video.duration; check(video.duration, video.duration); });
    return;
  }

  var yt = box.querySelector("[data-youtube-id]");
  if (yt) {
    window.onYouTubeIframeAPIReady = function () {
      var player = new YT.Player(yt, {
        videoId: yt.dataset.youtubeId,
        playerVars: { rel: 0, modestbranding: 1 },
        events: {
          onStateChange: function (event) {
            if (event.data === YT.PlayerState.ENDED) markWatched();
          },
        },
      });
      window.setInterval(function () {
        if (player && player.getCurrentTime) check(player.getCurrentTime(), player.getDuration());
      }, 1000);
    };
    var tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  }
})();
