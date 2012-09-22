swift-report
============

ln -s swift-report.py swift-report

This is mostly useful to identify "orphan" accounts in Swift with Keystone.
The output looks like this (the account without a name is an orphan):

  32586/248/7f4ade7dbbdee981b7335c787e6fc248 -K cdub
  15051/4a7/3acbbe2ab55b81269ff88490a1b574a7 SK zaitcev
  52389/69e/cca50f1c92b3b7f2a15d6b8e2aaee69e S- -
   3066/787/0bfa11e194ee8889ff1c797a718cf787 SK admin

Things you need to do before this is useful:

 * Pre-position swift-report-collect.py agent at all storage nodes.
   Adjust "collect_path" in swift-report.conf accordingly.

 * Of course, ssh must accept publickey auth, too.

 * Configure the admin account in Keystone so keystone user-list works.

 * Copy /etc/swift/account.ring.gz from the proxy node (or any node).
   Copy /etc/swift/swift.conf, too. That thing is hella secret, BTW.
