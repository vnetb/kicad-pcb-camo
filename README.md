# PCB Camouflage (KiCad Plugin)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![KiCad Version](https://img.shields.io/badge/KiCad-7.0--9.0-blue.svg)](https://www.kicad.org/)

自動車の開発車両（テストカー / プロトタイプ）に見られる**ダズル迷彩・渦巻き（スワール）カモフラージュパターン**を、KiCadの基板シルク層へ自動生成するプラグインです。

リバースエンジニアリング防止やプロトタイプ基板のデザイン向上に役立つだけでなく、**部品パッドの自動回避（クリアランス確保）**や**既存シルクの退避・ワンクリック復元**など、基板製造と実用性を考慮した機能を備えています。

---

## 主な機能

### 1. 開発車両風カモフラージュ生成
* **テストカー渦巻き（Test Mule Swirl）**: 有機的な渦巻き・スワール曲線パターン
* **幾何学ダズル迷彩（Geometric Dazzle）**: 角度を持った多角形・斜めブロックの直線迷彩
* **ゼブラストライプ（Zebra Waves）**: 流線型の波状ストライプ

### 2. パッド自動回避（はんだ付け安全設計）
* 対象面のSMDパッドおよび全スルーホールパッドを自動検出。
* 指定したクリアランス（例: デフォルト 0.4mm）を自動でくり抜き（Boolean Subtract）、はんだ付け面へのシルク乗りを完全に防止します。

### 3. 既存シルクの退避＆復元（Silk Stash & Restore）
* 迷彩生成時に邪魔になる部品番号（Reference）、定数（Value）、基板直描きテキスト・図形を、**未使用のユーザーレイヤー（`User.9 → User.8 → User.7 …` の降順で自動探索）**へ一時退避。
* 元に戻したい時は、`[ Restore Silkscreen ]` ボタン一発で元のシルクレイヤーへ完全復元可能。
* ユーザーレイヤーの `User.1, 2` や `Eco1, 2` を既に使用しているプロジェクトでも衝突せずに安全に利用できます。

### 4. ワンクリック削除・再生成
* 生成した迷彩パターンのみを検出し、一括削除・再生成が可能。
* KiCad標準のアンドゥ（`Ctrl + Z`）にも対応。

---

## 使い方

1. Pcbnew（基板エディタ）の上部ツールバーまたは「ツール」メニューから **PCB Camouflage** アイコンをクリックして起動します。
2. **Camouflage Generator タブ**:
   * 対象面（F.Silkscreen / B.Silkscreen）を選択します。
   * パターン種別（Swirl / Dazzle / Zebra）やスケール、パッドクリアランスを調整します。
   * 「Automatically stash existing silkscreen before generating」にチェックを入れると、既存シルクを自動退避してから迷彩を生成します。
   * **[ Generate Camouflage ]** をクリックします。
3. **Silk Stash & Restore タブ**:
   * いつでもシルクの手動退避（Stash）や復元（Restore）が行えます。

---

## インストール方法

### プラグイン＆コンテンツマネージャー (PCM) からのインストール
1. 本リポジトリの [Releases](../../releases) ページから、最新の **`kicad-plugin.zip`** をダウンロードします。
2. KiCad を起動し、メイン画面の **プラグイン＆コンテンツマネージャー**（Plugin and Content Manager）を開きます。
3. 画面右下の **「ファイルからインストール...」**（Install from File...）をクリックします。
4. ダウンロードした `kicad-plugin.zip` を選択します。
5. KiCad を再起動すると、Pcbnewのツールバーおよびメニューにアイコンが追加されます。

---

## ライセンス

MIT License
