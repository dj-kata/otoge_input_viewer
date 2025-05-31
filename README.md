# otoge input viewer
IIDXコントローラ(PHOENIX WANなど)の入力可視化、リリース速度や入力密度の表示が行えるソフトウェアです。
OBSへの設定をとても楽に行うことができます。  
らぐ様の[打鍵ディスプレイツール](https://rag-oji.com/dakendisplay/)の影響を多大に受けていますが、
IIDX以外のコントローラへの対応も考えており、立ち位置としては別物であるつもりです。

A tool for displaying inputs of IIDX-controller(eg. PHOENIX WAN, ...). It is easy to configure into OBS.
This tool is inspired from [dakendisplay tool](https://rag-oji.com/dakendisplay/).

![image](https://github.com/user-attachments/assets/adb1d85c-b1b8-4215-85db-04f68acb8037)
![image](https://github.com/user-attachments/assets/87d1efb2-db12-457f-9c6a-efb389f20146)

# Usage (ツールの利用方法)
1. [Releaseページ](https://github.com/dj-kata/otoge_input_viewer/releases)の一番上にあるotoge_input_viewer.zipをダウンロードして解凍する。
2. otoge_input_viewer.exeを実行する。
3. 検出するコントローラを変更したい場合は```changeボタン```を押す
4. OBSにキー入力状況を表示したい場合は、同梱のHTMLファイル(htmlフォルダ内)をOBSにドラッグ&ドロップする。
5. SDVXで使いたい場合やリリース計算に使うノーツ数を変更したい場合は設定画面(```メニューバー内config```)から設定を変更してください。

作者がPHOENIX WAN/FAUCE TWOしか持っていないため他のIIDXコンでの検証はできていません。

![image](https://github.com/user-attachments/assets/257ff66a-4ee7-4cf8-9353-ecf7600b29a8)  

設定画面では、
- コントローラの種別(IIDX, SDVX)
- それ以上長い入力をロングノーツとみなすためのしきい値
- リリース速度計算のために直近何ノーツを用いるか
- 譜面密度計算のために直近何秒のノーツを見るか

を設定することができます。

同梱のHTMLファイルについては以下の通りとなっています。
|ファイル名|推奨サイズ|内容|
|-|-|-|
|html/iidx_1p.html|400×250|IIDX 1P側|
|html/iidx_2p.html|400×250|IIDX 2P側|
|html/sdvx.html|300×250|SDVX|


また、本アプリの新バージョンがリリースされた際には、
アプリ起動時にアップデート機能が動くようになっています。


## デザインのカスタマイズ
現状では、以下のような背景画像の設定のみ行うことができます。  
![image](https://github.com/user-attachments/assets/0f86d5e6-4900-439d-9502-ef4bc091018d)  

以下の手順で設定できます。
1. ```html```フォルダ内に背景画像を置く。(ここでは、ファイル名を```bg.png```とします。)
2. ディスプレイ表示用のブラウザソースをダブルクリックし、カスタムCSSに以下を追加してOKをクリック。

```css
.background{
    background-image: url("./bg.png");
}
```
ちなみに、背景画像を少し暗くしたい場合は以下にするとできます。
rgba(0,0,0,0.65)の4つ目が不透明度で、この値が大きいほど暗くなります。適宜調整してください。
```css
.background{
    background-image: linear-gradient(rgba(0,0,0,0.65),rgba(0,0,0,0.65)),url(bg.png);
}
```
![image](https://github.com/user-attachments/assets/67e215a1-64ac-489c-b92f-09ca29f1ccd4)

# 対応状況など
PHOENIXWAN 2022+でのみ動作確認しています。

DAO FP2007だと動かないことが分かっています。(一部キーに対するイベントが特殊なため、対応できない可能性が高いです)  
他にも上手く拾えないコントローラがあったら[作者のTwitter](https://x.com/cold_planet_)に教えていただけると助かります。(ログの送付をお願いするかもしれません)

XMLファイルに書き込んだデータをOBSで拾う仕組みで動くため、
書き込み速度の遅いHDDなどでは密度が高いシーンでの描画が遅れるかもしれません。

# 今後の予定
アプリ-ブラウザ間通信(ajax)がファイルIOを経由するため性能的に厳しい可能性が高く、
方式を変更する可能性が高いです。SDVX, IIDX DP対応とともに出せたらと考えています。

また、以下機能を追加するかもしれません。

- IIDX DPでの動作
- SOUND VOLTEXでの動作
- ボタン部分に画像を埋め込むための仕組み
- カスタムCSSでできることの追加
  - ボタンや皿部分への画像の追加
  - 押下時の光り方のカスタマイズ

# その他
不具合報告などについては、
本レポジトリのIssuesまたは[作者のTwitter](https://x.com/cold_planet_)へお願いします。

配信へのクレジット表記などは別に必須ではないですが、書いてもらえると喜びます。
```
Otoge Input Viewer
https://github.com/dj-kata/otoge_input_viewer
```
