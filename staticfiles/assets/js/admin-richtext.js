/* Turns <textarea class="richtext"> in the admin into a full rich-text
   editor. Loaded only by the About form (see AboutForm.Media). */
document.addEventListener("DOMContentLoaded", () => {
  if (typeof tinymce === "undefined") return;

  const dark = document.documentElement.dataset.bsTheme === "dark";

  // Django rejects a POST without this, so read it off the cookie
  function csrfToken() {
    const hit = document.cookie.match(/(^|;\s*)csrftoken=([^;]*)/);
    return hit ? decodeURIComponent(hit[2]) : "";
  }

  tinymce.init({
    selector: "textarea.richtext",
    height: 560,
    menubar: "edit view insert format table",
    branding: false,
    promotion: false,
    plugins:
      "advlist autolink lists link image media table charmap anchor searchreplace " +
      "visualblocks visualchars code fullscreen insertdatetime preview wordcount " +
      "codesample emoticons nonbreaking pagebreak directionality quickbars",
    toolbar:
      "undo redo | blocks fontfamily fontsize | " +
      "bold italic underline strikethrough | forecolor backcolor removeformat | " +
      "alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | " +
      "link image media table codesample blockquote hr | " +
      "charmap emoticons | preview fullscreen code",
    toolbar_mode: "sliding",
    quickbars_selection_toolbar: "bold italic link h2 h3 blockquote",
    contextmenu: "link image table",
    image_caption: true,
    image_advtab: true,
    table_default_attributes: { class: "richtext-table" },
    paste_data_images: false, // upload instead of embedding megabytes of base64

    skin: dark ? "oxide-dark" : "oxide",
    content_css: dark ? "dark" : "default",

    /* Uploads go to the about app, which stores the file and answers with
       { "location": "<url>" } — the shape TinyMCE expects. */
    images_upload_handler: (blobInfo) =>
      new Promise((resolve, reject) => {
        const body = new FormData();
        body.append("file", blobInfo.blob(), blobInfo.filename());

        fetch("/about/upload", {
          method: "POST",
          body,
          headers: { "X-CSRFToken": csrfToken() },
        })
          .then((res) => (res.ok ? res.json() : Promise.reject(res)))
          .then((data) => resolve(data.location))
          .catch(async (res) => {
            let msg = "Upload failed.";
            try {
              msg = (await res.json()).error || msg;
            } catch { /* not JSON — keep the default message */ }
            reject({ message: msg, remove: true });
          });
      }),
  });
});
