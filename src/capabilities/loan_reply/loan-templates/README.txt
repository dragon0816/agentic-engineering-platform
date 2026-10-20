儀器借出單回信範本
==================

這個資料夾裡的 .txt 檔會【覆寫】程式內建的信件文字。

  * 檔案不存在 = 用內建預設。刪掉檔案就回到預設，不會壞掉。
  * 只想改一封信，就只留那一個檔，其他刪掉。
  * 存檔後【立即生效】，不需要重啟 Host Bridge、也不需要重新安裝。
  * 用 Notepad 編輯就可以，存成 UTF-8（有沒有 BOM 都可以）。

placeholder 寫成 {名稱}，會被實際內容取代。打錯名字時 job 會停下來並告訴你
是哪個檔案、哪個名稱、以及那個檔案可以用哪些名稱 —— 不會靜靜地在客戶信裡留白。

要在信裡寫出真正的大括號，請寫兩次：{{ 和 }}。

各檔案可用的 placeholder
------------------------
blocked-reply.txt
    {borrowNo}  {category}  {classificationDeliveryBlock}  {customerEmail}  {customerId}  {customerName}  {customerRaw}  {deliveryBlock}  {loanUrl}  {signature}
customer-not-found-body.txt
    {borrowNo}  {category}  {customerEmail}  {customerId}  {customerName}  {customerRaw}  {loanUrl}  {reason}  {reasonDetail}  {reasonHeadline}  {signature}
customer-not-found-subject.txt
    {borrowNo}  {category}  {customerEmail}  {customerId}  {customerName}  {customerRaw}  {loanUrl}  {reason}  {reasonDetail}  {reasonHeadline}  {signature}
failure-body.txt
    {borrowNo}  {borrowNoOrUnknown}  {category}  {customerEmail}  {customerId}  {customerName}  {customerRaw}  {error}  {loanUrl}  {signature}
failure-subject.txt
    {borrowNo}  {borrowNoOrUnknown}  {category}  {customerEmail}  {customerId}  {customerName}  {customerRaw}  {error}  {loanUrl}  {signature}
shipping-reply.txt
    {borrowNo}  {category}  {customerEmail}  {customerId}  {customerName}  {customerRaw}  {loanUrl}  {signature}
