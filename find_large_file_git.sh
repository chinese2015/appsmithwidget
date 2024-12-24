git log --pretty=format:"%H" | while read commit_hash; do
  echo "Checking commit $commit_hash"
  git ls-tree -r $commit_hash | awk '{print $3}' | while read file; do
    file_size=$(git cat-file blob $commit_hash:$file | wc -c)
    if [ $file_size -gt 10000000 ]; then   # 例如，检查大于 10MB 的文件
      echo "Large file found: $file ($file_size bytes) in commit $commit_hash"
    fi
  done
done
